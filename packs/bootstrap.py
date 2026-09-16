"""The executable form of packs/README.md's own "two-agent split" section
-- what the Bootstrap agent (1-CYCLE.md Phase 0) actually runs to offer
the pillar combinations, and what the Builder agent runs to read the
handoff.

Six commands:

  python -m packs.bootstrap list-pillars
      Prints every adoptable pillar and every non-empty combination of
      them, generated from packs/*.yaml's own `pillar:`/`description:`
      fields -- never hardcoded prose that could drift from those files
      the moment a pack changes. This is the literal menu Phase 0 step 2
      (1-CYCLE.md, Gate 35) requires offering explicitly for a genuinely
      new ecosystem root, never defaulted to silently.

  python -m packs.bootstrap questions [--answers-file FILE] [--all]
      Prints the ONE next question to ask -- id, text, kind
      (closed/open_with_default/open_with_options/open), and its real
      option set, if any -- as concrete data, never a question already
      answered, and never one whose precondition isn't met yet. `pillars`,
      `project_kind`, `app_runtimes`, `use_git`, `location` are
      unconditional -- asked for every pillar combination, since none of
      them describe the Bridge specifically. Everything else needs BOTH `pillars` and
      `app_runtimes` answered first, and comes in one of two mutually
      exclusive pairs per runtime: `bridge_language_backend`/
      `bridge_language_frontend` when Bridge IS among `pillars`, or
      `app_language_backend`/`app_language_frontend` when it's NOT --
      never both for the same runtime. Without --answers-file: the very
      first question (`pillars`). With one (a JSON object of
      `{question_id: answer}` accumulated so far, updated with the new
      answer and re-passed after EVERY question): the next one after
      that.

      RUN THIS AGAIN AFTER EVERY SINGLE ANSWER, in a loop, until it
      prints "Nothing left to ask." -- never ask more than one question
      per invocation, and never assume you already know what comes next
      without re-running it. This one-at-a-time default exists because
      of a real, observed bug: an agent ran this command once, saw a
      few unconditional questions all at once, asked all of them, and
      moved on WITHOUT re-running it after `pillars` and `app_runtimes`
      were answered -- the Bridge-language questions behind them never
      got asked at all, because they only become visible once `pillars`
      names "bridge" AND `app_runtimes` names a matching runtime, and
      nothing forced a re-check.
      `--all` prints the full remaining list instead, for a human
      skimming the flow or previewing what's left -- never what an
      agent actually driving the live flow should act on. QUESTIONS
      below is the one place each question's real option set is
      declared -- read it here, once, never re-typed into a prompt.

  python -m packs.bootstrap resolve --ecosystem-root PATH --pillars-file FILE
      --project-kind {new,existing} --app-runtimes {backend,frontend,both}
      --use-git {yes,no} [--app-language-backend TEXT]
      [--app-language-frontend TEXT] [--combine-with-file FILE]
      [--out PATH] [--resolved-by NAME]
      Writes a new ecosystem-resolution record
      (ecosystem-resolution-record.schema.json,
      blueprint.dep.ecosystem_resolution) from a `pillars-file` -- a JSON
      file matching the schema's own `pillars` object shape directly,
      the same posture blueprint.dep.finish_cycle's own CLI already takes
      toward --cycle-report/--verification-record (a real record as a
      file, never flattened into ad hoc flags -- `pillars.bridge` in
      particular is a variable-length array of multi-field objects, which
      no flag design handles cleanly). Exits 0 with the written path on
      stdout, or 1 with why not on stderr (schema-invalid input, OR --
      real, observed failure -- ecosystem_root has no actual files
      copied/ported into it yet: this refuses rather than writing a
      record that describes an ecosystem that doesn't exist). When
      `--use-git yes`, ALSO calls `ensure_git_repo` right after a
      successful write and prints its result -- a real `git init`, not
      just a note in the record.

  python -m packs.bootstrap describe PATH
      Pretty-prints an existing resolution record -- which pillars, what
      each resolved to, which combine_with hooks were applied. What
      the Builder agent runs first, instead of hand-reading raw JSON, to
      confirm what the Bootstrap agent actually settled before building
      anything.

  python -m packs.bootstrap check-scope --ecosystem-root PATH
      [--resolution-record PATH]
      Scans PATH for files/directories structurally shaped like the
      Bridge pillar's own contract/manifest model (contracts/,
      capabilities/, a manifest.yaml with capability_id+implementations,
      capability-catalog.jsonl) when the resolution record says Bridge
      was NOT adopted -- exits 0 clean or 1 naming every match. Run this
      anytime during Phase 1-7, not just once at the very end:
      blueprint/dep/finish_cycle.py runs the same underlying check
      (ecosystem_resolution.detect_bridge_leakage) as a hard publish-time
      gate, but catching this earlier means less to undo. Exists because
      packs/README.md's own "No Bridge means no capability vocabulary"
      prose, alone, was not enough -- a real Builder agent built a full
      contracts/capabilities tree for a DEP+Cycles-only resolution
      anyway.

  python -m packs.bootstrap ensure-git --ecosystem-root PATH
      Makes PATH a real git working tree if it isn't one already (`git
      init`); does nothing if it already is. Idempotent, non-fatal if
      git isn't on PATH (reports that instead of raising). `resolve
      --use-git yes` already calls this once automatically -- run it
      again standalone anytime to confirm, or if `--use-git` was
      answered after the fact.

Nothing here duplicates a pack's own content -- `list-pillars` reads
packs/*.yaml directly every time, so it can never go stale independently
of them. `questions`' own option sets (e.g. the Bridge-language
questions' one reference-language option) are also declared once, in
QUESTIONS below, not re-typed into packs/README.md's own prose walkthrough
of the same flow -- that walkthrough exists for a human reading the
file, and points here for what an agent actually asking these questions
should run.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from blueprint.dep import ecosystem_resolution

_PACKS_DIR = Path(__file__).resolve().parent


def _load_pack_descriptions() -> dict[str, dict[str, str]]:
    """pillar name (lowercase) -> {"pack": ..., "display": ..., "description": ...},
    read fresh from every packs/*.yaml sibling of this file each call --
    never cached, never copied into this module's own source. `display`
    is the pack's own `pillar:` field verbatim (e.g. "DEP", not "Dep") --
    used for anything printed to a human/agent, never re-derived with
    `.capitalize()` or similar, which would mangle an acronym like DEP.
    """

    result: dict[str, dict[str, str]] = {}
    for path in sorted(_PACKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        result[data["pillar"].lower()] = {
            "pack": data["pack"],
            "display": data["pillar"],
            "description": data["description"].strip(),
        }
    return result


def list_pillars() -> None:
    pillars = _load_pack_descriptions()
    names = sorted(pillars)

    print("Available pillars (packs/README.md):")
    for name in names:
        first_line = pillars[name]["description"].splitlines()[0]
        print(f"  - {pillars[name]['display']} ({pillars[name]['pack']}.yaml): {first_line}")
    print()

    print("Combinations you can adopt (choose one):")
    n = 1
    for r in range(1, len(names) + 1):
        for combo in itertools.combinations(names, r):
            label = " + ".join(pillars[c]["display"] for c in combo)
            if r == len(names):
                label += "  (the full, integrated configuration -- see starterkit/)"
            print(f"  {n}. {label}")
            n += 1


# The Bootstrap agent's own question sequence (packs/README.md "Starting
# the Bootstrap agent"), in order. Each entry:
#   id       -- stable key, also the answers-file key in --answers-file.
#   text     -- the question to ask, verbatim, standalone -- never bundle
#               it with the reasoning for what happens after an answer.
#   kind     -- "closed" (a small finite set, no free text needed),
#               "open_with_default" (one real, well-justified option +
#               a free-text fallback -- never a second option that just
#               restates the free-text fallback, that's redundant),
#               "open_with_options" (more than one real option + a
#               free-text fallback, same rule), or "open" (no options at
#               all -- nothing sensible to suggest, e.g. an absolute
#               path; ask plainly).
#   options  -- the real option set for "closed"/"open_with_default"/
#               "open_with_options"; None for "open". For "closed", this
#               is the complete answer set (no free text). For the other
#               two, a free-text fallback always exists ALONGSIDE these
#               -- never declare a redundant option duplicating it.
#   options_source -- present ONLY when `options` is None but real
#               options still exist elsewhere (today: just `pillars`,
#               whose live menu is list_pillars()'s own job, not
#               duplicated here). Absent (not None -- the key itself
#               missing) for every other question: for "closed" questions
#               it would be redundant with `options` already being the
#               full set; for "open", it would be actively wrong -- there
#               genuinely is no menu to point at. Never read `options is
#               None` alone as "ask in plain text" -- check this field
#               first, since for `pillars` it means the opposite: still a
#               selection question, the options just live in a second
#               command's own output instead of here.
#   applies  -- callable(answers: dict) -> bool. `answers` maps id ->
#               whatever was actually answered so far (see below for the
#               exact expected shape per id).
_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "pillars",
        "text": "Which pillar combination?",
        "kind": "closed",
        "options": None,
        "options_source": "python -m packs.bootstrap list-pillars",
        "applies": lambda a: True,
    },
    {
        "id": "project_kind",
        "text": "Is this a brand-new project, or are you adding this pillar combination to an existing one?",
        "kind": "closed",
        "options": ["new", "existing"],
        # Changes what the Builder actually DOES after this flow, not just
        # what gets copied -- "existing" means merge the adopted pillar(s)'
        # own tooling into a project that's already there: never invent
        # placeholder/example application code, never restructure anything
        # already present beyond what adopting the pillar(s) genuinely
        # requires (packs/README.md's own "existing project" paragraph has
        # the concrete rules). Recorded verbatim in the ecosystem-resolution
        # record's own top-level `project_kind` -- never left for the
        # Builder to guess from what it happens to find on disk. Real,
        # observed failure this exists to prevent: given an existing
        # project, a Builder scaffolded an entire fake application from
        # scratch instead of recognizing there was nothing to build.
        "applies": lambda a: True,
    },
    {
        "id": "app_runtimes",
        "text": "Does this project have a backend, frontend, or both?",
        "kind": "closed",
        "options": ["backend", "frontend", "both"],
        # A property of the APPLICATION, not of the Bridge -- asked
        # regardless of which pillars are adopted. "No Bridge" doesn't
        # mean "no backend or no frontend": a DEP+Cycles-only project can
        # still have a real backend and/or frontend, in some language,
        # with no Bridge capability-execution pattern involved at all.
        # Only the Bridge-language questions right below (and, for
        # Bridge, which files get copied) are gated on Bridge being
        # adopted -- this one never is.
        "applies": lambda a: True,
    },
    {
        "id": "bridge_language_backend",
        "text": "What language should the backend Bridge be written in?",
        "kind": "open_with_default",
        "options": ["Python"],  # starterkit/'s own reference implementation
        "applies": lambda a: "bridge" in (a.get("pillars") or ()) and a.get("app_runtimes") in ("backend", "both"),
    },
    {
        "id": "bridge_language_frontend",
        "text": "What language should the frontend Bridge be written in?",
        "kind": "open_with_default",
        "options": ["JavaScript"],  # starterkit/'s own reference implementation
        "applies": lambda a: "bridge" in (a.get("pillars") or ()) and a.get("app_runtimes") in ("frontend", "both"),
    },
    {
        "id": "app_language_backend",
        "text": "What language should the backend be written in, if you already know?",
        "kind": "open_with_default",
        "options": ["Not yet / I don't know"],
        # Mutually exclusive with `bridge_language_backend`, never both:
        # with a Bridge, the Bridge itself IS the backend's own language
        # boundary (`bridge_language_backend` already answers this)
        # -- asking again would be redundant and could contradict it.
        # Without one, there's no reference language to suggest the way
        # `bridge_language_backend` suggests "Python" -- a Bridge-free
        # backend can be anything, hence the plain fallback option.
        "applies": lambda a: "bridge" not in (a.get("pillars") or ()) and a.get("app_runtimes") in ("backend", "both"),
    },
    {
        "id": "app_language_frontend",
        "text": "What language should the frontend be written in, if you already know?",
        "kind": "open_with_default",
        "options": ["Not yet / I don't know"],
        "applies": lambda a: "bridge" not in (a.get("pillars") or ()) and a.get("app_runtimes") in ("frontend", "both"),
    },
    {
        "id": "use_git",
        "text": "Do you want this project to use git for version control?",
        "kind": "closed",
        "options": ["yes", "no"],
        # Independent of every pillar -- version control is a property of
        # the project, not of any adopted pillar. Worth asking explicitly
        # rather than silently assuming: DEP's own git-aware tooling
        # (blueprint/dep/state_ref.py's `vcs` probe,
        # blueprint/dep/git_commit_event.py) only produces anything if the
        # project is a REAL git repository, and both already fail
        # gracefully rather than loudly when it isn't -- a "yes" answer
        # that never actually got `git init` run would silently get that
        # same graceful-nothing forever, for a reason the user never
        # chose. See `ensure_git_repo()` below: a "yes" here is a real
        # action taken (git init, if not already a repo), not just a fact
        # noted in the resolution record.
        "applies": lambda a: True,
    },
    {
        "id": "location",
        "text": "Where should the new project live?",
        "kind": "open",
        "options": None,  # no sensible default to suggest -- ask plainly, never propose a path
        "applies": lambda a: True,
    },
]


def applicable_questions(answers: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Returns exactly what to ask next, in order: the subset of
    `_QUESTIONS` NOT already present (by `id`) in `answers` AND whose
    `applies(answers)` is true, each as a plain JSON-serializable dict
    (no callable) -- `id`/`text`/`kind`/`options`, plus `options_source`
    when present (today: only `pillars`). Never returns a question
    already answered, even if it would still "apply" -- once something
    is known, it's known.

    `options: None` is NOT itself "ask in plain text" -- check for
    `options_source` first. Its presence means real options exist, just
    generated by a second command instead of listed here (`pillars`);
    its absence on an `options: None` question means genuinely open,
    nothing to select from at all (`location`).

    `answers` is `{}`/None for the very start (nothing decided yet):
    only questions with no precondition show up then (`pillars`,
    `project_kind`, `app_runtimes`, `location` -- all four unconditional).
    Every other question needs BOTH `pillars` and `app_runtimes` answered
    first, and is one of exactly two mutually exclusive kinds per runtime,
    never both for the same runtime: `bridge_language_backend`/
    `bridge_language_frontend` when Bridge IS among `pillars` (the Bridge
    itself is that runtime's own language boundary), or
    `app_language_backend`/`app_language_frontend` when it's NOT (nothing
    else would ever answer "what language is this runtime in" otherwise)
    -- which pair applies depends only on `pillars`; which member(s) of
    that pair depend on `app_runtimes` naming that runtime
    (backend/frontend/both), same rule for both pairs.

    Expected value per id, when present: `pillars` a list of lowercase
    pillar names; `project_kind` one of "new"/"existing"; `app_runtimes`
    one of "backend"/"frontend"/"both"; the rest are free text and don't
    affect any other question's `applies`.
    """

    answers = answers or {}
    result = []
    for q in _QUESTIONS:
        if q["id"] in answers or not q["applies"](answers):
            continue
        item = {"id": q["id"], "text": q["text"], "kind": q["kind"], "options": q["options"]}
        if "options_source" in q:
            item["options_source"] = q["options_source"]
        result.append(item)
    return result


def next_question(answers: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    """The ONE next question to ask -- the first item of
    `applicable_questions(answers)`, or `None` once nothing is left
    (every applicable question has been answered).

    Drive off THIS, in a loop, not `applicable_questions()`'s full
    remaining list -- seeing several questions at once invites asking
    more than one before re-checking, which is exactly how a real,
    observed run skipped questions entirely: both Bridge-language
    questions never got asked because the agent queried once, saw the
    handful of unconditional questions, asked all of them, and moved on
    without ever re-running the command after `pillars` and
    `app_runtimes` were answered to discover what THOSE unlocked. Call
    this, ask its `text`, get a real answer, write `{id: answer}` into
    your answers file, call this again -- stop only once it returns
    `None`. Never skip a re-check because you think you already know
    what comes next.
    """

    remaining = applicable_questions(answers)
    return remaining[0] if remaining else None


def _print_one_question(q: dict[str, Any]) -> None:
    print(f"[{q['id']}] ({q['kind']}) {q['text']}")
    if q["options"]:
        for opt in q["options"]:
            print(f"    - {opt}")
    elif "options_source" in q:
        print(f"    (still a selection question -- run `{q['options_source']}` for the real options)")


def print_questions(answers: Optional[dict[str, Any]] = None, show_all: bool = False) -> None:
    """Default (`show_all=False`): prints ONLY `next_question(answers)`
    -- the one thing to ask right now, or "Nothing left to ask." This is
    the mode the Bootstrap agent should actually run, in a loop (see
    `next_question`'s own docstring for why). `show_all=True` (the CLI's
    `--all`) prints the full remaining list instead -- a preview/
    reference view, e.g. for a human skimming what the flow could still
    ask, never what an agent driving the live flow should act on one
    question at a time from.
    """

    if not show_all:
        q = next_question(answers)
        if q is None:
            print("Nothing left to ask.")
            return
        _print_one_question(q)
        return

    questions = applicable_questions(answers)
    if not questions:
        print("Nothing left to ask.")
        return
    for q in questions:
        _print_one_question(q)


def _has_real_content_besides_state(ecosystem_root: Path) -> bool:
    """True if `ecosystem_root` exists and has at least one entry other
    than a `state` directory -- the cheapest, most generic possible
    signal that SOMETHING was actually copied (or ported) into it, as
    opposed to nothing at all. Doesn't know or check anything about
    WHICH files should be there for a given pillar combination (that's a
    real judgment call for whoever did the copying, not something this
    function second-guesses) -- it only catches the total-absence case:
    an ecosystem_root that's missing entirely, or contains nothing but
    the `state/` directory `resolve()` itself is about to write into.
    """

    if not ecosystem_root.exists():
        return False
    return any(entry.name != "state" for entry in ecosystem_root.iterdir())


def ensure_git_repo(ecosystem_root: Path) -> str:
    """Makes `ecosystem_root` a real git working tree when the Bootstrap
    `use_git` question was answered "yes" -- a real action taken, not a
    fact recorded and left for someone else to act on (the same
    discipline packs/README.md's own "actually copy the files" already
    established for pillar files). Returns a short, human-readable status
    string; NEVER raises -- git is optional infrastructure DEP's own
    tooling already treats as best-effort
    (blueprint/dep/state_ref.py's own `vcs` probe never fails the caller
    over a missing git, `blueprint/dep/git_commit_event.py`'s posture is
    the deliberate inverse, loud, because THAT module's whole job is
    recording a real git action that must have already happened) -- this
    one is closer to state_ref's posture: report, don't crash a Bootstrap
    flow over git being absent.

    Three outcomes:
      - `ecosystem_root` is already a real git working tree (`git
        rev-parse --is-inside-work-tree` succeeds) -- does nothing,
        reports that.
      - It isn't yet, and `git` is on PATH -- runs `git init` there,
        reports confirmation.
      - `git` isn't installed/on PATH at all -- reports that instead of
        raising; whoever is driving the Bootstrap flow decides whether to
        install git and re-run, or proceed without it.
    """

    ecosystem_root = ecosystem_root.resolve()
    # Created BEFORE any subprocess call, unconditionally -- a
    # not-yet-existing cwd would make `run()` fail with the SAME OSError
    # a genuinely-missing git binary produces, misreporting "git is not
    # available" for what's actually "this directory doesn't exist yet".
    ecosystem_root.mkdir(parents=True, exist_ok=True)

    def run(*args: str) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                ["git", *args], cwd=str(ecosystem_root), capture_output=True, text=True, timeout=10.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    probe = run("rev-parse", "--is-inside-work-tree")
    if probe is None:
        return f"git is not available on PATH -- install it, then run `git init` in {ecosystem_root} yourself."
    if probe.returncode == 0 and probe.stdout.strip() == "true":
        return f"{ecosystem_root} is already a git repository -- nothing to do."

    init_result = run("init")
    if init_result is not None and init_result.returncode == 0:
        return f"initialized a new git repository at {ecosystem_root}."
    detail = (init_result.stderr.strip() or init_result.stdout.strip()) if init_result is not None else "git init could not be run"
    return f"`git init` failed in {ecosystem_root}: {detail}"


def resolve(
    ecosystem_root: Path,
    pillars_file: Path,
    project_kind: str,
    app_runtimes: str,
    use_git: str,
    app_language_backend: Optional[str] = None,
    app_language_frontend: Optional[str] = None,
    combine_with_file: Optional[Path] = None,
    out: Optional[Path] = None,
    resolved_by: Optional[str] = None,
) -> Path:
    """Builds and saves a new ecosystem-resolution record. `pillars_file`
    is a JSON file holding exactly the schema's own `pillars` object
    (e.g. `{"process": {...}, "evolution": {...}}`) -- whichever pillars
    were chosen after `list_pillars()` presented the options. `project_kind`
    is `"new"` or `"existing"` (the `project_kind` question's own answer,
    schema-validated to exactly those two values) -- stored verbatim,
    never inferred from what's actually found under `ecosystem_root`: for
    `"existing"`, this check below will typically pass trivially (the
    existing project's own files already satisfy it before any pillar
    adoption even starts) -- that's expected, not a loophole; the real
    governance for `"existing"` is behavioral, not this check (never
    invent placeholder application code, packs/README.md's own "existing
    project" paragraph). `app_runtimes` is that matching Bootstrap
    question's own answer, ALSO stored verbatim -- real, observed failure
    this param fixes: the question was asked and answered, but the answer
    was never written into the record anywhere, so the Builder agent had
    no way to know it. `use_git` (`"yes"`/`"no"`, that matching question's
    own answer) is stored the same way. This function itself only
    RECORDS `use_git` -- it never calls `ensure_git_repo` itself, staying
    a pure record-writer (no subprocess side effects to account for when
    testing `resolve` in isolation); the `resolve` CLI command is what
    actually calls `ensure_git_repo(ecosystem_root)` right after a
    successful resolve when `use_git` is `"yes"`, printing its result.
    A caller using this function directly (not the CLI) that wants the
    same real action should call `ensure_git_repo` itself.
    `app_language_backend`/`app_language_frontend` are
    each `None` UNLESS the matching `app_language_backend`/
    `app_language_frontend` Bootstrap question was actually asked and
    answered -- which only happens when Bridge is NOT among `pillars`
    (with a Bridge, that runtime's own `bridge_language_backend`/
    `bridge_language_frontend` answer already covers this, reflected in
    `pillars.bridge.runtimes[].language`; recording it twice would risk
    the two ever disagreeing). Never pass a value here just because one
    happens to be known -- pass `None` whenever the matching question
    never actually applied, so the record's own `app_language` key stays
    absent exactly when `pillars.bridge.runtimes[].language` is the
    single source of truth instead. Raises
    ecosystem_resolution.EcosystemResolutionError if the resulting record
    fails schema validation (an empty `pillars`, a malformed runtime
    entry, an unknown pillar key, a `project_kind` other than "new"/
    "existing", an `app_runtimes` other than "backend"/"frontend"/"both"),
    OR if `ecosystem_root` shows no real evidence that any
    pack files were actually copied or ported into it yet (see
    `_has_real_content_besides_state`) -- a real, observed failure this
    refusal exists to catch: an agent ran every question, got real
    answers, then called this function directly, WITHOUT ever doing the
    copy/port step packs/README.md's own closing paragraph describes,
    producing a fully schema-valid record naming files (e.g.
    `starterkit/backend/runtime/bridge/bridge.py`, copied verbatim from
    THIS repo's own source paths) that don't exist anywhere under the
    target ecosystem_root at all. A resolution record describing an
    ecosystem that doesn't actually exist is worse than refusing to
    write one -- same "fail closed" posture finish_cycle already has
    toward an unverified cycle. Returns the path written to.

    `ecosystem_root` is always resolved to an absolute path before it's
    either stored in the record or used to derive the default `out`
    path -- a relative path (e.g. "my-app") would be stored verbatim
    otherwise, ambiguous the moment anything reads it back from a
    different working directory than whichever one `resolve()` happened
    to run from (2-RULES.md "No silent defaults on what resolution
    depends on"). This never fails on a not-yet-existing directory
    *by itself* -- `Path.resolve()` doesn't require the path to exist,
    only makes it absolute and normalizes `.`/`..` segments -- but a
    not-yet-existing directory always fails the real-content check above,
    as it should: nothing has been copied into a directory that isn't
    even there yet (and, for `project_kind="existing"`, a genuinely
    not-yet-existing directory is itself a contradiction worth surfacing
    as this same refusal, not a separate error).
    """

    ecosystem_root = ecosystem_root.resolve()
    if not _has_real_content_besides_state(ecosystem_root):
        raise ecosystem_resolution.EcosystemResolutionError(
            f"{ecosystem_root} has no real content yet (it's missing entirely, or holds nothing "
            "but a state/ directory) -- copy (or port) the chosen pack(s)' files into it FIRST "
            "(packs/README.md \"Starting the Bootstrap agent\", the paragraph after every "
            "question is answered), then call resolve. Do not call resolve as a substitute for "
            "actually copying anything."
        )
    pillars = json.loads(pillars_file.read_text(encoding="utf-8"))
    record: dict[str, Any] = {
        "resolution_id": f"res-{uuid.uuid4().hex[:12]}",
        "ecosystem_root": str(ecosystem_root),
        "project_kind": project_kind,
        "app_runtimes": app_runtimes,
        "use_git": use_git,
        "pillars": pillars,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    app_language: dict[str, str] = {}
    if app_language_backend is not None:
        app_language["backend"] = app_language_backend
    if app_language_frontend is not None:
        app_language["frontend"] = app_language_frontend
    if app_language:
        record["app_language"] = app_language
    if combine_with_file is not None:
        record["combine_with_applied"] = json.loads(combine_with_file.read_text(encoding="utf-8"))
    if resolved_by is not None:
        record["resolved_by"] = resolved_by

    out_path = out if out is not None else ecosystem_root / "state" / "ecosystem-resolution.json"
    return ecosystem_resolution.save_resolution_record(record, out_path)


def describe(path: Path) -> None:
    record = ecosystem_resolution.load_resolution_record(path)
    if record is None:
        print(f"No resolution record at {path}", file=sys.stderr)
        raise SystemExit(1)

    print(f"resolution_id:  {record['resolution_id']}")
    print(f"ecosystem_root: {record['ecosystem_root']}")
    print(f"project_kind:   {record['project_kind']}")
    print(f"app_runtimes:   {record['app_runtimes']}")
    print(f"use_git:        {record['use_git']}")
    if "app_language" in record:
        for runtime, language in record["app_language"].items():
            print(f"app_language:   {runtime}: {language}")
    print(f"resolved_at:    {record['resolved_at']}")
    if "resolved_by" in record:
        print(f"resolved_by:    {record['resolved_by']}")
    print(f"pillars adopted: {', '.join(sorted(record['pillars']))}")
    for name, detail in record["pillars"].items():
        print(f"  {name}:")
        for key, value in detail.items():
            print(f"    {key}: {value}")

    hooks = record.get("combine_with_applied") or []
    if hooks:
        print("combine_with_applied:")
        for hook in hooks:
            mark = "x" if hook["applied"] else " "
            print(f"  [{mark}] {hook['hook']} ({hook['from_pillar']} -> {hook['to_pillar']}): {hook.get('detail', '')}")


def check_scope(ecosystem_root: Path, resolution_record_path: Optional[Path] = None) -> list[str]:
    """The proactive half of the same check `finish_cycle` now runs as a
    hard publish-time gate (blueprint/dep/finish_cycle.py,
    ecosystem_resolution.detect_bridge_leakage) -- run this ANYTIME during
    Phase 1-7, not just at Phase 8 publish time, so a Builder agent
    catches Bridge-shaped leakage (contracts/, capabilities/,
    manifest.yaml with capability_id+implementations,
    capability-catalog.jsonl) the moment it's created, not several phases
    later when finish_cycle finally refuses to publish. Real, observed
    failure both checks exist for: a Builder agent, given a
    DEP+Cycles-only resolution with no Bridge pillar adopted at all, built
    a full contracts/capabilities tree anyway -- packs/README.md's own
    prose telling it not to was not enough on its own.

    Reads the resolution record at `resolution_record_path` (default:
    `<ecosystem_root>/state/ecosystem-resolution.json`, `resolve()`'s own
    default `out` path) to find out whether Bridge was actually adopted --
    if it was, this returns `[]` unconditionally: a real contracts/
    directory is exactly what a Bridge-adopting ecosystem is SUPPOSED to
    have, never a violation. Only scans for leakage when Bridge is NOT
    among the resolved `pillars`. Raises
    ecosystem_resolution.EcosystemResolutionError (via
    load_resolution_record) if no record exists yet or it fails schema
    validation -- this check needs to know what was actually resolved,
    never guesses.
    """

    record_path = resolution_record_path if resolution_record_path is not None else ecosystem_root / "state" / "ecosystem-resolution.json"
    record = ecosystem_resolution.load_resolution_record(record_path)
    if record is None:
        raise ecosystem_resolution.EcosystemResolutionError(
            f"no resolution record at {record_path} -- run `resolve` first (packs/README.md "
            "\"Starting the Bootstrap agent\"); this check needs to know which pillars were "
            "actually adopted before it can tell leakage from a legitimate Bridge adoption."
        )
    if "bridge" in record["pillars"]:
        return []
    return ecosystem_resolution.detect_bridge_leakage(ecosystem_root)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m packs.bootstrap",
        description="Offer/resolve/describe a project's own pillar combination (1-CYCLE.md Phase 0 Gate 25/35).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-pillars", help="Print the available pillars and every combination of them.")

    p_questions = sub.add_parser("questions", help="Print the ONE next question to ask. Run again after every answer.")
    p_questions.add_argument(
        "--answers-file", type=Path, default=None,
        help="JSON object of {question_id: answer} answered so far -- prints the next question after those. Omit to see the very first question.",
    )
    p_questions.add_argument(
        "--all", action="store_true",
        help="Print every remaining question at once instead of just the next one -- a preview/reference view, not what a live-running Bootstrap agent should act on.",
    )

    p_resolve = sub.add_parser("resolve", help="Write a new ecosystem-resolution record.")
    p_resolve.add_argument(
        "--ecosystem-root", required=True, type=Path,
        help="Absolute or relative -- always resolved to absolute before being stored, so a relative path is safe to pass but never required.",
    )
    p_resolve.add_argument(
        "--pillars-file", required=True, type=Path,
        help="JSON file matching the schema's own 'pillars' object shape directly.",
    )
    p_resolve.add_argument(
        "--project-kind", required=True, choices=["new", "existing"],
        help="The project_kind question's own answer -- whether ecosystem-root is a brand-new project or an already-existing one this pillar combination is being added to. Never defaulted.",
    )
    p_resolve.add_argument(
        "--app-runtimes", required=True, choices=["backend", "frontend", "both"],
        help="The app_runtimes question's own answer. Recorded even with no Bridge adopted -- there is nowhere else it would ever be written down.",
    )
    p_resolve.add_argument(
        "--use-git", required=True, choices=["yes", "no"],
        help="The use_git question's own answer. \"yes\" makes this command also run "
        "ensure_git_repo(ecosystem-root) right after a successful resolve -- a real git init, not "
        "just a note in the record.",
    )
    p_resolve.add_argument(
        "--app-language-backend", default=None,
        help="The app_language_backend question's own answer, if it was actually asked (Bridge NOT among --pillars-file's own pillars, and --app-runtimes names backend/both). Omit entirely when it wasn't -- never pass a guessed value.",
    )
    p_resolve.add_argument(
        "--app-language-frontend", default=None,
        help="Same as --app-language-backend, for app_language_frontend.",
    )
    p_resolve.add_argument("--combine-with-file", type=Path, default=None)
    p_resolve.add_argument("--out", type=Path, default=None, help="Default: <ecosystem-root>/state/ecosystem-resolution.json")
    p_resolve.add_argument("--resolved-by", default=None)

    p_describe = sub.add_parser("describe", help="Pretty-print an existing ecosystem-resolution record.")
    p_describe.add_argument("path", type=Path)

    p_check_scope = sub.add_parser(
        "check-scope",
        help="Scan an ecosystem for Bridge-shaped leakage (contracts/, capabilities/, manifests) "
        "when the Bridge pillar was never adopted. Run this anytime during Phase 1-7, not just at "
        "Phase 8 publish time (finish_cycle runs the same check as a hard gate there).",
    )
    p_check_scope.add_argument("--ecosystem-root", required=True, type=Path)
    p_check_scope.add_argument(
        "--resolution-record", type=Path, default=None, dest="resolution_record_path",
        help="Default: <ecosystem-root>/state/ecosystem-resolution.json",
    )

    p_ensure_git = sub.add_parser(
        "ensure-git",
        help="Make --ecosystem-root a real git working tree if it isn't one already (git init). "
        "Idempotent -- safe to run again anytime, e.g. to double-check after `resolve --use-git yes` "
        "already ran it once.",
    )
    p_ensure_git.add_argument("--ecosystem-root", required=True, type=Path)

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.command == "list-pillars":
        list_pillars()
        return 0

    if args.command == "questions":
        answers = None
        if args.answers_file is not None:
            answers = json.loads(args.answers_file.read_text(encoding="utf-8"))
        print_questions(answers, show_all=args.all)
        return 0

    if args.command == "resolve":
        try:
            out_path = resolve(
                args.ecosystem_root, args.pillars_file, args.project_kind,
                args.app_runtimes, args.use_git, args.app_language_backend, args.app_language_frontend,
                args.combine_with_file, args.out, args.resolved_by,
            )
        except ecosystem_resolution.EcosystemResolutionError as exc:
            print(f"bootstrap resolve: refused -- {exc}", file=sys.stderr)
            return 1
        print(out_path)
        if args.use_git == "yes":
            print(ensure_git_repo(args.ecosystem_root))
        return 0

    if args.command == "describe":
        describe(args.path)
        return 0

    if args.command == "check-scope":
        try:
            leaks = check_scope(args.ecosystem_root, args.resolution_record_path)
        except ecosystem_resolution.EcosystemResolutionError as exc:
            print(f"bootstrap check-scope: {exc}", file=sys.stderr)
            return 1
        if not leaks:
            print("No pillar-scope leakage found.")
            return 0
        print(f"Bridge-shaped leakage found with no Bridge pillar adopted ({len(leaks)}):", file=sys.stderr)
        for leak in leaks:
            print(f"  {leak}", file=sys.stderr)
        return 1

    if args.command == "ensure-git":
        print(ensure_git_repo(args.ecosystem_root))
        return 0

    return 1  # unreachable -- argparse enforces one of the subcommands above


if __name__ == "__main__":
    raise SystemExit(main())
