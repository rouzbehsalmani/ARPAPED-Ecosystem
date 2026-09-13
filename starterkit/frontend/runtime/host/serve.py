"""Local static file server for ../ (this runtime's own browser-facing
files -- index.html, app.js, bridge/, capabilities/, capability-catalog.jsonl).

Lives under runtime/, not implementation/, despite being build/dev-style
tooling in spirit: implementation/ is defined as "never shipped, never
needed by a real deployment" (../../README.md's Layout), and that's
exactly wrong for this file -- an actual deployment of this frontend
DOES need something serving ../ over HTTP (this script, or nginx, or any
other static host), the same way the backend's own deployment needs
`../app/main.py` actually running, not merely available at build time.
It lives in its own `host/` subfolder rather than flat alongside
index.html/app.js/etc. because it plays a different role from those:
this script is never itself fetched by a browser, it's the thing that
makes everything else in ../ fetchable in the first place -- worth
keeping visually separate from the files a client actually loads.

Prefer this over a bare `python -m http.server` (see ../../README.md
"Run"): Python's http.server derives Content-Type from the `mimetypes`
module, which on Windows reads the OS registry first -- and many Windows
installs map `.js` to `text/plain` there (a long-standing stdlib quirk,
confirmed on one such machine: `mimetypes.guess_type("x.js")` returned
`text/plain`, not a JavaScript type). A browser refuses to execute a
`<script type="module">` whose response Content-Type isn't a JavaScript
MIME type ("Failed to load module script ... text/plain") -- so
index.html loads, but every import inside it silently fails, and the
page's own error handling (index.html's assembly try/catch) never even
runs because the script itself never started. Not fixable in the served
files; the fix belongs in how they're served.

Any other real static file server (nginx, `npx serve`, etc.) already sets
correct types itself and works too -- this one exists purely so
`python -m ...` "just works" cross-platform for this starter kit, out of the
box, on the one platform where the stdlib's own default doesn't.

Run from the repository root:
    python -m starterkit.frontend.runtime.host.serve [port]
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parent.parent

# Only the extensions this runtime actually serves (index.html, app.js,
# bridge/*.js, capabilities/**/executor.js, capability-catalog.jsonl) --
# everything else still falls through to the platform's own guess below.
_FORCED_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".html": "text/html",
    ".json": "application/json",
    ".jsonl": "application/json",
}


class _Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        forced = _FORCED_TYPES.get(Path(path).suffix)
        return forced if forced is not None else super().guess_type(path)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8421
    handler = partial(_Handler, directory=str(_RUNTIME_ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Serving {_RUNTIME_ROOT} at http://127.0.0.1:{port} -- Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
