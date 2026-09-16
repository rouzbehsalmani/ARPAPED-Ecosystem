# The `log` app (frontend)

One app under `runtime/apps/` — this starter kit's own worked example,
mirroring `../../../../backend/runtime/apps/log/` on the frontend side.
A second app would get its own sibling directory here
(`runtime/apps/<name>/`), with its own `app.js`/`index.html`, resolving
against the SAME frontend Bridge Core and capability catalog at
`runtime/` (never a per-app copy of either).

## What this app does

`index.html` runs its own Bridge Core entirely in the browser
(`../../bridge/core.js`). Clicking the button calls `client.log`
(Local — executes right here, in this page's own JavaScript), which
itself depends on `log.write` (Remote — a real cross-origin HTTP POST to
the backend's `/bridge` endpoint). See `index.html`'s own inline comments
for the full request/response story.

## Files

- `app.js` — this app's single request-construction point (R6, the JS
  mirror of `starterkit/backend/runtime/apps/requests.py`): builds
  the Bridge Core, assembles every implementation from
  `runtime/capability-catalog.jsonl` (shared, not copied here), exposes
  `resolve(name, operation)`.
- `index.html` — the page a real client loads; imports `app.js` as an ES
  module.

## Run

Needs the whole `runtime/` tree served (not just this folder — the
Bridge Core, capability catalog, and executor assets it depends on all
live one level up). From the repository root:
```
python -m starterkit.frontend.runtime.host.serve
```
then open `http://127.0.0.1:8421/apps/log/` in a browser. See
`../../../README.md` ("Run") for the backend's own half and the two
servers together.
