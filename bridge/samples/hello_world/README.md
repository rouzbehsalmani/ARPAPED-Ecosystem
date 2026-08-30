# Sample: hello world console app

The simplest possible complete, runnable example of the pattern
`0-WALKTHROUGH.md` describes: one capability (`console.write`), a single
request-construction point, and a process entry point that decides nothing —
laid out in the same `contracts/` / `capabilities/<domain>/<operation>/` /
`app/` structure the walkthrough recommends for any real application.

This is scaffolding to prove the wiring, not a feature — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern), never this domain content, into a real capability.

## Layout

```
contracts/
  console.write.contract.yaml    the capability's contract artifact (schema-valid)
capabilities/
  console/write/
    manifest.yaml                 binds the contract to the executor below
    executor.py                   registration-unaware: given text, writes it to the console
app/
  requests.py                     the single request-construction point (R6)
  main.py                         the entry point — decides nothing, calls one capability
```

## Run

From the repository root:

```
python -m bridge.samples.hello_world.app.main
```

Expected output: `Hello, world!` — printed by the executor, not by `app/main.py`.
