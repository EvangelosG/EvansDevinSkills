---
name: angular-to-react-migration
description: Migrate an Angular application to React + TypeScript on Vite by running a four-stage dynamic workflow (scaffold, foundation, per-component fan-out, combine). Use when asked to port, migrate or rewrite an Angular app in React.
---

# Angular -> React, as a dynamic workflow

`workflow.py` next to this file is the whole procedure. Run it with the `run_workflow`
tool; this file explains what it assumes, what to do before and after it, and the
failure modes that cost a run.

```bash
# from the Angular checkout, on a fresh branch
REPO_DIR=/path/to/checkout   # exported for the run_workflow call
```

```
run_workflow(workflow_name="angular-to-react",
             script_path=".../.agents/skills/angular-to-react-migration/workflow.py")
```

Invoke the builtin `dynamic-workflows` skill first — it owns the runtime API and the
resume semantics this workflow relies on.

## Nothing here is app-specific

Configuration is two environment variables, and both have defaults:

```bash
REPO_DIR=$PWD        # the Angular checkout
APP_DIR=src/app      # Angular sources root inside it
```

Everything else — which components exist, which services are stateless HTTP wrappers and
which are stateful, the models, the pipes, the guards, the route files — is discovered by
walking the checkout, and the discovered inventory is injected into the prompts. The
target layout (`components/`, `services/`, `context/`, `models/`, styles, routes) is not
hardcoded either: stage 0 chooses it and reports it, and every later prompt is built from
that answer.

## The shape, and why it is this shape

| Stage | Agents | Owns |
| --- | --- | --- |
| -1 reference | 1 | runs the **Angular** app and screenshots every route/state, **before anything is deleted** |
| 0 scaffold | 1 | Vite + React + tsconfig, package.json purge, Angular config deletion, **publishes the src/ layout** |
| 1 foundation | 1 | models, pipes, services -> fetch/Promise modules, stateful services -> context + hook, **publishes exact signatures** |
| 2 components | one per `*.component.ts` | one triplet each -> `.tsx` + `.module.scss`, deletes the original |
| 3 combine | 1 | routing, global/theme SCSS, PWA, hosting/CI config, build + **screenshot-diff** verification, deletes leftovers |

Stages 0/1 are barriers on purpose. The fan-out is only safe because the shared
dependencies already exist with **known names**: stage 1's structured output (import
specifiers, function signatures, hook API) goes verbatim into all N component prompts, so
eleven agents that never see each other still call the same `fetchFeed(feedType, page)`
and the same `useSettings()`. Skip that and they each invent an API.

Stage 3 is a barrier because it consumes the component manifest (name, path, prop
interface) to wire routing and composition.

The reference stage exists because the migration is destructive: stage 2 deletes each
triplet it ports, so from that moment the original app cannot be run or looked at again.
Its screenshots (in `~/.devin-angular-react/<repo>/reference-screenshots/`) are the
acceptance criteria — stage 3 walks them one by one and diffs the React app against each,
and component agents consult the ones showing their component. "Feature parity" with no
runnable original is guesswork; this is what makes it checkable.

It also does the **global-stylesheet hazard audit**: bare element selectors nested under
theme/layout classes (`.night .wrapper a {}`) outrank component class selectors, so the
list is collected once up front and injected into every component prompt rather than
rediscovered as visual bugs at the end.

## What the prompts enforce

Beyond the mechanical `*ngIf` -> JSX table, the prompts carry the rules for things Angular
did implicitly and React does not. These are the migration's actual bug surface:

- **CSS scoping** (`CSS_RULES`, into stages 2 and 3) — `ViewEncapsulation` has no React
  equivalent, so: no bare element selectors at the top level of a component stylesheet;
  child combinators so a parent's `a {}` cannot reach into a child component; check the
  component that *renders* yours for colliding element selectors (a dialog inside a header
  inherits `.header h1 {}`); beat theme-nested element selectors with an id or
  `!important` and set `:visited`; percentage widths and `display: block` now measure
  against the full parent; conditionally-rendered components need their SCSS imported from
  an always-mounted parent or Vite injects it too late.
- **Fetch/state correctness** — `res.ok` before `res.json()` *and* treating an HTTP 200
  body carrying an `error` field as a failure; stale-response cancellation in every
  fetching `useEffect`; persisted state read in the `useState` initialiser, never in an
  effect (otherwise the default flashes first); `DOMPurify` for every
  `dangerouslySetInnerHTML`; never nest `<Link>` inside `<a>`.
- **Angular features beyond the common four** — guards/resolvers, `loadChildren` ->
  `React.lazy`, `HttpInterceptor` -> one shared fetch wrapper, `@angular/animations` -> CSS
  transitions toggled by state, `ng-content` -> `children` / named `ReactNode` props,
  `@ViewChild` -> `useRef` or lifted state, `@HostListener`/`@HostBinding`, forms ->
  controlled inputs, and `Router.events` pageview tracking -> `useLocation` + `useEffect`
  with a `useRef` guard so a `/` redirect is not double-counted.

## Shared VM, not separate VMs

Every agent runs `vm_mode="shared"`: one checkout, no git handoff, and the orchestrator
commits at the end. That is the right trade here because the stages are edits to a single
tree that must typecheck together — passing 11 branches around and merging them would be
most of the work.

It is only safe because **file ownership is disjoint**: each fan-out agent may touch only
its own triplet and the two files it creates. The prompts say so explicitly, and the
sibling-name list is passed in so an agent imports a not-yet-written sibling at the
conventional path instead of creating its own copy. Keep that property if you edit the
prompts; two agents on one file will silently clobber each other.

Corollaries baked into `COMMON_RULES`: the reference stage is the only one that installs
and serves the *Angular* app (and edits nothing), stage 0 is the only one that installs the
React dependencies, stage 3 is the only one that builds and serves the React app, and no
agent runs a state-changing git command.

## Resumability

`agent()` calls are keyed by prompt hash, so a resumed run only replays if the prompts are
byte-identical. Two things would otherwise break that, and both are handled:

- **The reference screenshots and the inventory both live outside the checkout**, under
  `~/.devin-angular-react/<repo>/`, so a resume neither rescans nor tries to re-photograph
  an app whose sources are gone.
- **The inventory is cached** to `~/.devin-angular-react/<repo>/inventory.json` on the
  first run. Stage 2 deletes the triplets it ports, so a re-glob on resume would return a
  shorter list and change every prompt. Delete that file to force a rescan.
- Embedded JSON is dumped with `sort_keys=True` everywhere.

Resume with `run_workflow(run_id="wfr-...")`; completed agents return instantly.

A stage-2 agent that dies is caught, recorded as `file_path: "FAILED"` in the manifest,
and handed to stage 3 to port itself, so one bad agent does not sink the run.

## What the orchestrator still does by hand

1. Create the branch before the run (the agents will not).
2. After the run: verify `npm run build` yourself, then `git add -A` and commit — the
   diff is a whole-app rewrite, so review the summary rather than the 100+ files.
3. Open the PR, then hand UI verification to the testing agent. Stage 3 diffs against its
   own reference screenshots; the testing agent is the adversarial pass on top of that.
4. Update the repo blueprint: the Angular `test`/`lint` commands in it are now wrong
   (Karma is gone and there is usually no test script at all).

## Cost and timing

Measured on a small app (11 components, angular2-hn) **without** the reference stage:
**~7 minutes wall clock end to end**, because stage 2's eleven agents run concurrently and
each has one small triplet to port. Stages 0, 1 and 3 are the long poles. The reference
stage and the screenshot diffing in stage 3 add serial browser time — budget more like
30-45 minutes for the pair, which is the price of a checkable parity claim.

## Failure modes seen in a real run

| Symptom | Cause / fix |
| --- | --- |
| Components each invent their own API client | Stage 1's structured output was vague. Its signatures must be full TypeScript signatures, not prose. |
| A resume starts every agent fresh | The inventory rescanned, or a prompt embeds an unsorted dict. |
| Global theme styles stop applying | A component agent CSS-moduled a class that global SCSS targets. Component-scoped styles only; theme class names stay global strings. |
| `npm run build` passes but a route is blank | Stage 3 only checks the routes it knows about. Hand the PR to the testing agent. |
| Input/panel much wider in React than Angular | A `width: %` or `display: block` that ViewEncapsulation used to constrain. Fixed sizing. |
| A modal renders unstyled the first time it opens | Vite injected its CSS on first mount; import that SCSS from an always-mounted parent. |
| Fixing one component's CSS breaks a sibling | Overriding a shared parent selector. Re-check parent/children/siblings after every CSS fix. |
| Error UI never appears for bad input | Some APIs answer HTTP 200 with `{"error": ...}`. The ported fetch wrapper must treat that as a failure — stage 3's prompt says so, but check it. |
| Sass build errors after the theme migration | `@use` module system: `/` division -> `math.div`, `darken()` -> `color.adjust`. |

## Devin Secrets Needed

None.
