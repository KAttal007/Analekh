# Analekh Excel add-in (Phase 5)

Office.js task pane that shows change sets and assumptions beside the open model (design doc
13.3, 19.2). Until Phase 5 the xlwings bridge (`python -m analekh.excel_bridge`) is the Excel path.

Part of the pnpm workspace at the repository root (`pnpm install` there installs it too).

```bash
pnpm --filter analekh-excel-addin dev-certs   # trust a localhost HTTPS certificate (Office requires HTTPS)
pnpm --filter analekh-excel-addin start       # sideload into desktop Excel
```

Install scripts of three Microsoft 365 sign-in dependencies are denied in `pnpm-workspace.yaml`
(`allowBuilds`). If sideloading fails because of one of them, set it to `true` there and run
`pnpm install` again.
