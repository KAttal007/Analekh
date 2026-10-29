"""Production proxy chain keeps the real client address (security audit run-1).

Caddy -> nginx (web) -> uvicorn: the per-address sign-in limit only works when uvicorn takes the
client address from X-Forwarded-For, and only from the web container.
"""

import ipaddress
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_api_trusts_forwarded_for_only_from_the_web_container():
    compose = yaml.safe_load((ROOT / "deploy/compose.production.yml").read_text())
    web_ip = compose["services"]["web"]["networks"]["default"]["ipv4_address"]
    ipam = compose["networks"]["default"]["ipam"]["config"][0]
    assert ipaddress.ip_address(web_ip) in ipaddress.ip_network(ipam["subnet"])
    # dynamic addresses come from ip_range, so no other container can take web's address first
    assert ipaddress.ip_address(web_ip) not in ipaddress.ip_network(ipam["ip_range"])
    args = compose["services"]["api"]["command"].split()
    assert "--proxy-headers" in args
    assert args[args.index("--forwarded-allow-ips") + 1] == web_ip


def test_nginx_passes_caddys_forwarded_for_to_the_api():
    conf = (ROOT / "web/nginx.conf").read_text()
    assert "proxy_set_header X-Forwarded-For $http_x_forwarded_for;" in conf


def test_nginx_body_cap_covers_the_highest_admin_upload_limit():
    """nginx's 1 MB default would refuse uploads the admin allows; the API enforces the real limit."""
    import re

    from analekh.config import get_settings

    s = get_settings()
    match = re.search(r"client_max_body_size\s+(\d+)m;", (ROOT / "web/nginx.conf").read_text())
    assert match is not None
    assert int(match.group(1)) * 1024 * 1024 >= s.max_upload_ceiling_bytes + s.request_body_overhead_bytes
