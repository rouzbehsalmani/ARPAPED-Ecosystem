"""Process entry point (R1): decides nothing, constructs no request --
resolves through app/requests.py and calls the handle it returns.

Three calls, each resolved by a declared name (app/dependencies.yaml),
never a restated contract_version/implementation_id:
  1-2. log_write (unpinned -> log.write.default) -- the highest-priority
       policy-allowed candidate for this name wins; plain, then
       `level: "warn"`.
  3. log_write_process -- log.write again, from a genuinely different,
     out-of-process implementation (executor_kind: process, written in
     C# for this example; named for that, not the language) -- proves
     the process executor protocol is language-neutral.

Then starts web.serve -- an API endpoint ONLY (/bridge), never static
files: the frontend is served separately, by its own static host, not by
this process (../../../README.md "Two servers, not one" -- nothing can
resolve a capability through a Bridge before its own hosting page has
already loaded, so serving that page can never itself be reached through
the Bridge it exists to bootstrap). See ../../README.md "Run" for this
half's own build/run steps, and ../../../README.md "Two servers, not
one" for the two commands together. Ctrl+C stops the API server cleanly.

This entry point's own startup/shutdown status ("API running at...",
"server stopped") is logged through the SAME `log` handle as the three
calls above -- a real backend logs its own lifecycle through its logger,
not a bare `print()`, now that `log.write` is real domain content rather
than a disposable placeholder. The frontend-serving instructions
immediately after stay a plain `print()` deliberately: that's CLI
guidance for the human at this terminal, not an event this service would
ever log on its own.

Run from the repository root (build the C# executor first -- see
capabilities/log/write_process/manifest.yaml):
    python -m starterkit.backend.runtime.app.main
"""

from starterkit.backend.runtime.app.requests import resolve


def main():
    log = resolve("log_write", "write")
    log.call({"message": "This is a test of the Bridge's log.write capability."})
    log.call({"message": "Something worth flagging.", "level": "warn"})

    log_process = resolve("log_write_process", "write")
    log_process.call({"message": "This line is printed by a second process, through the Bridge.", "level": "error"})

    server = resolve("web_serve", "start")
    result = server.call({"host": "127.0.0.1", "port": 8420})
    log.call({"message": f"API running at {result.output['url']} (/bridge). Ctrl+C to stop."})
    print("Now serve the frontend separately, e.g.:")
    print("    python -m starterkit.frontend.runtime.host.serve")
    print("then open http://127.0.0.1:8421 in a browser.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        resolve("web_serve", "stop").call({})
        log.call({"message": "server stopped"})


if __name__ == "__main__":
    main()
