"""Strip noise from graphify-out/graph.json, merge small communities, rewrite the report.

Runs after every graphify rebuild (hook); idempotent. By hand: <graphify python> scripts/graphify_clean.py
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "graphify-out" / "graph.json"
CONFIG_FILES = (
    "package.json",
    "tsconfig.json",
    ".prettierrc.json",
    "schema.d.ts",
    "pnpm-workspace.yaml",
)


MIN_GROUP = 40  # smaller communities merge into a neighbour
MAX_GROUP = 220  # merges never exceed this size
TEST_SUFFIXES = (".test.ts", ".test.tsx", "/conftest.py")


def is_test_file(src: str) -> bool:
    return ("/" + src).find("/tests/") >= 0 or src.endswith(TEST_SUFFIXES)


def merge_small(G, comms: dict[int, list]) -> dict[int, list]:  # noqa: ANN001
    groups = {cid: list(members) for cid, members in comms.items()}
    home = {n: cid for cid, members in groups.items() for n in members}
    stuck: set[int] = set()
    while True:
        small = [c for c in groups if len(groups[c]) < MIN_GROUP and c not in stuck]
        if not small:
            break
        cid = min(small, key=lambda c: len(groups[c]))
        ties = collections.Counter(home[m] for n in groups[cid] for m in G.neighbors(n) if home[m] != cid)
        fits = [(k, c) for c, k in ties.most_common() if len(groups[c]) + len(groups[cid]) <= MAX_GROUP]
        if not fits:
            stuck.add(cid)
            continue
        into = fits[0][1]
        for n in groups.pop(cid):
            home[n] = into
            groups[into].append(n)
    pooled: dict[str, list] = {}
    for cid in [c for c in groups if len(groups[c]) < MIN_GROUP]:
        members = groups.pop(cid)
        pooled.setdefault(folder_label(G, members), []).extend(members)
    ordered = sorted([*groups.values(), *pooled.values()], key=len, reverse=True)
    return dict(enumerate(ordered))


def folder_label(G, members: list) -> str:  # noqa: ANN001
    folders: collections.Counter[str] = collections.Counter()
    for n in members:
        parts = str(G.nodes[n].get("source_file") or "").replace("\\", "/").split("/")[:-1]
        if parts:
            folders["/".join(parts[: 3 if parts[0] in ("web", "office-addin") else 2])] += 1
    if folders:
        return folders.most_common(1)[0][0]
    top = max(members, key=G.degree)
    return str(G.nodes[top].get("label", top))[:40]


def _triggered_by_rebuild() -> bool:
    if sys.stdin is None or sys.stdin.isatty():
        return True
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return True
    cmd = str((payload.get("tool_input") or {}).get("command", ""))
    return not cmd or "graphify update" in cmd or "graphify hook" in cmd or "graphify.watch" in cmd


HOOK_FILES = ("post-commit", "post-checkout", "post-merge", "post-rewrite")
HOOK_CALL = "__import__('subprocess').run([sys.executable, 'scripts/graphify_clean.py', '--quiet'], check=False)  # analekh: strip noise nodes"
REBUILD_CALLS = (
    "_rebuild_code(_root, changed_paths=changed, force=_force)",
    "_rebuild_code(_root, force=_force)",
)


def _graphify_python() -> str | None:
    candidates: list[Path] = []
    tools = os.environ.get("UV_TOOL_DIR") or subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=False).stdout.strip()
    if tools:
        for sub in ("Scripts/python.exe", "bin/python"):
            candidates.append(Path(tools) / "graphifyy" / sub)
    saved = ROOT / "graphify-out" / ".graphify_python"
    if saved.is_file():
        candidates.append(Path(saved.read_text(encoding="utf-8").strip()))
    for py in candidates:
        if py.is_file():
            return str(py)
    try:
        import graphify  # noqa: F401
    except ImportError:
        return None
    return sys.executable


def install_hooks(py: str) -> int:
    hooks_dir = ROOT / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print("no .git/hooks here")
        return 1
    subprocess.run([py, "-m", "graphify", "hook", "install"], cwd=ROOT, check=False)
    for name in HOOK_FILES:
        path = hooks_dir / name
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        if any("graphify_clean.py" in ln for ln in lines):
            print(f"{name}: already patched")
            continue
        out: list[str] = []
        patched = False
        for ln in lines:
            out.append(ln)
            if ln.strip() in REBUILD_CALLS:
                out.append(ln[: len(ln) - len(ln.lstrip())] + HOOK_CALL)
                patched = True
        if patched:
            path.write_text("\n".join(out), encoding="utf-8", newline="\n")
        print(f"{name}: {'patched' if patched else 'NO rebuild call found, left as is'}")
    return 0


def main() -> int:
    quiet = "--quiet" in sys.argv
    say = (lambda *_: None) if quiet else print
    forced = "--forced" in sys.argv  # set by the parent after it already checked the trigger
    if "--install-hooks" not in sys.argv and not forced and not _triggered_by_rebuild():
        return 0
    py = _graphify_python()
    if py is None:
        say("graphify_clean: graphify not found (uv tool install graphifyy)")
        return 0
    if "--install-hooks" in sys.argv:
        return install_hooks(py)
    if py != sys.executable:  # run again under the interpreter that has graphify
        cmd = [py, str(Path(__file__).resolve()), *sys.argv[1:], "--forced"]
        return subprocess.run(cmd, check=False).returncode
    if not GRAPH.is_file():
        return 0

    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect
    from graphify.export import to_json
    from graphify.paths import out_path
    from graphify.report import generate
    from graphify.watch import _read_build_excludes, _read_build_gitignore
    from networkx.readwrite import json_graph

    os.chdir(ROOT)
    raw = json.loads(GRAPH.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(raw, edges="links")
    G.graph["hyperedges"] = raw.get("hyperedges", [])
    before = (G.number_of_nodes(), G.number_of_edges())

    drop: dict[str, list[str]] = collections.defaultdict(list)
    for nid, d in G.nodes(data=True):
        src = str(d.get("source_file") or "").replace("\\", "/")
        if not src:
            drop["external/unresolved"].append(nid)
        elif is_test_file(src):
            drop["test files"].append(nid)
        elif src.endswith(CONFIG_FILES):
            drop["config-file keys"].append(nid)
        elif str(d.get("label", "")).endswith("__init__.py") and G.degree(nid) <= 1:
            drop["empty __init__ stubs"].append(nid)
        elif G.degree(nid) == 0:
            drop["isolated"].append(nid)
    if not drop:  # already clean, unless small communities could still be merged
        shown: dict[int, list] = collections.defaultdict(list)
        for nid, d in G.nodes(data=True):
            shown[d.get("community", -1)].append(nid)
        if len(merge_small(G, shown)) == len(shown):
            say("graphify_clean: nothing to do")
            return 0

    G.remove_nodes_from({n for v in drop.values() for n in v})
    orphans = [n for n in G if G.degree(n) == 0]  # left alone by the removals above
    G.remove_nodes_from(orphans)
    if orphans:
        drop["isolated"].extend(orphans)
    G.graph["hyperedges"] = [h for h in G.graph["hyperedges"] if sum(1 for n in h.get("nodes", []) if n in G) >= 3]

    comms = merge_small(G, cluster(G))
    cohesion = score_all(G, comms)
    labels = {cid: folder_label(G, members) for cid, members in comms.items()}
    seen = collections.Counter(labels.values())
    nth: collections.Counter[str] = collections.Counter()
    for cid in sorted(labels):
        if seen[labels[cid]] > 1:
            nth[labels[cid]] += 1
            labels[cid] = f"{labels[cid]} ({nth[labels[cid]]})"

    out = out_path()
    detection = detect(ROOT, extra_excludes=_read_build_excludes(out), gitignore=_read_build_gitignore(out))
    cost_file = ROOT / "graphify-out" / "cost.json"
    cost = json.loads(cost_file.read_text(encoding="utf-8")) if cost_file.is_file() else {}
    tokens = {
        "input": cost.get("total_input_tokens", 0),
        "output": cost.get("total_output_tokens", 0),
    }
    questions = suggest_questions(G, comms, labels)
    if not to_json(G, comms, str(GRAPH), force=True, community_labels=labels):
        say("graphify_clean: graph.json write refused")
        return 1
    report = generate(
        G, comms, cohesion, labels, god_nodes(G), surprising_connections(G, comms),
        detection, tokens, ".", suggested_questions=questions,
    )  # fmt: skip
    (ROOT / "graphify-out" / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    (ROOT / "graphify-out" / ".graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")
    if "--html" in sys.argv or (ROOT / "graphify-out" / "graph.html").is_file():
        subprocess.run(
            [sys.executable, "-m", "graphify", "export", "html"],
            cwd=ROOT, check=False, capture_output=True,
        )  # fmt: skip

    removed = ", ".join(f"{len(v)} {k}" for k, v in drop.items())
    nodes, edges = G.number_of_nodes(), G.number_of_edges()
    say(f"graphify_clean: {before[0]}->{nodes} nodes, {before[1]}->{edges} edges ({removed}); {len(comms)} communities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
