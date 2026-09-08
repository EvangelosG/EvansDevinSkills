---
name: angular-to-react-migration
description: Migrate any Angular application to React + TypeScript on Vite by running a five-stage dynamic workflow (reference screenshots, scaffold, foundation, per-component fan-out, combine). Use when asked to port, migrate or rewrite an Angular app in React.
---

# Angular -> React, as a dynamic workflow

`workflow.py` next to this file is the whole procedure. Run it with the `run_workflow`
tool; this file explains what it assumes, what to do before and after it, and the
failure modes that cost a run.

## Running it

Invoke the builtin `dynamic-workflows` skill first — it owns the runtime API and the
resume semantics this workflow relies on. Then, from a fresh branch in the Angular
checkout:

```
run_workflow(workflow_name="angular-to-react",
             script_path=".../.agents/skills/angular-to-react-migration/workflow.py")
```

A user who wants this run on some other repo asks for it like this, and Devin does the
rest (clone both, branch, run, commit, PR):

> Migrate the Angular app in `owner/repo` to React. Clone `EvangelosG/EvansDevinSkills`
> and follow its `angular-to-react-migration` skill — run its `workflow.py` with
> `run_workflow`, `REPO_DIR` pointed at the checkout. Open a PR when it's done.

Or copy this directory into the target repo's `.agents/skills/` once, after which
"migrate this app to React" matches the skill on its own.

## Nothing here is app-specific

Configuration is two environment variables and neither is normally set:

```bash
REPO_DIR=$PWD    # the Angular checkout (default: cwd)
APP_DIR=...      # override the sources root; only for layouts angular.json does not describe
```

The sources root comes from `angular.json` — `defaultProject` first, else the first
application project, using its `sourceRoot` (and its `app/` subdirectory if there is one).
Only if there is no usable `angular.json` does it fall back to guessing `src/app`.

The inventory is then read **from the source, not the filenames**. Every `.ts` under the
root (minus `*.spec.ts`/`*.d.ts`) is classified by the decorator it carries:

| Found | Classified as |
| --- | --- |
| `@Component` | a fan-out unit; its template and stylesheets come from the actual `templateUrl`/`styleUrl(s)` values, so inline templates and non-adjacent files are handled |
| `@Injectable` | a service — or a **guard** if it implements `CanActivate`/`CanMatch`/`CanDeactivate`/`Resolve` |
| `@Pipe` / `@Directive` / `@NgModule` | pipe / directive / module |
| no decorator, guard interface or `*Fn` type | a functional guard |
| no decorator, no `@angular/*` import, only `export interface/type/enum/class` | a model |
| an import from `@ngrx/*`, `@ngxs/*`, `@datorama/akita`, `@ngneat/elf` | store state (takes precedence over `model`, which would mean "copy unchanged") |
| `: Routes` or `RouterModule.forRoot/forChild` | a route file (also flagged on decorated files) |
| anything else | `other` — tokens, constants, environments |

So it does not care whether the app follows the style guide's `header.component.ts` or
Angular 20's `header.ts`, whether models live in `models/` or `types/`, or whether the
stylesheet is named after the component. Fan-out labels come from the class name
(`HeaderComponent` -> `header`), disambiguated by folder when two components share a name.

The target layout (`components/`, `services/`, `context/`, `models/`, styles, routes) is
not hardcoded either: stage 0 chooses it and reports it, and every later prompt is built
from that answer.

Verified to produce an identical inventory on `angular2-hn` and on a copy of it renamed to
Angular 20 conventions, and to resolve the right source root, guards, directives, inline
templates and duplicate class names in a multi-project (Nx-style) `angular.json`.

`test_workflow.py` next to this file covers discovery and prompt composition by running
the whole workflow against stub agents on synthetic checkouts — `python3 -m unittest
test_workflow` from this directory, no dependencies. Run it after editing `workflow.py`.

## The shape, and why it is this shape

| Stage | Agents | Owns |
| --- | --- | --- |
| -1 reference | 1 | runs the **Angular** app and screenshots every route/state, **before anything is deleted** |
| 0 scaffold | 1 | Vite + React + tsconfig, package.json purge, Angular config deletion, **publishes the src/ layout** |
| 1 foundation | 1 | models, pipes, services -> fetch/Promise modules, stateful services -> context + hook, **publishes exact signatures** |
| 2 components | one per discovered `@Component` | one component each -> `.tsx` + `.module.scss`, deletes the original .ts/template/styles |
| 3 combine | 1 | routing, global/theme SCSS, PWA, hosting/CI config, build + **screenshot-diff** verification, deletes leftovers |

Stages 0/1 are barriers on purpose. The fan-out is only safe because the shared
dependencies already exist with **known names**: stage 1's structured output (import
specifiers, function signatures, hook API) goes verbatim into all N component prompts, so
eleven agents that never see each other still call the same `fetchFeed(feedType, page)`
and the same `useSettings()`. Skip that and they each invent an API.

Stage 3 is a barrier because it consumes the component manifest (name, path, prop
interface) to wire routing and composition.

The reference stage exists because the migration is destructive: stage 2 deletes each
component it ports, so from that moment the original app cannot be run or looked at again.
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
- **A store, if the app has one** (`STORE_RULES`, injected into stages 1 and 2 *only* when
  the inventory found one, so store-less apps keep their prompts and their cached runs).
  NgRx/NGXS/Akita/Elf become Redux Toolkit: one `createSlice` per reducer keeping the state
  field names, selectors as `createSelector`, effects as `createAsyncThunk` with the
  pending/fulfilled/rejected cases the effect's success/failure actions used to carry, and
  `store.select | async` / `store.dispatch` as typed `useAppSelector`/`useAppDispatch`.
  Entity adapters flatten to normalised state and router-store is dropped for
  `useParams`/`useLocation`. The store is why this is a *barrier*, not a rule: stage 1 ports
  it and publishes `store_api` (slices, state shape, selectors, actions, hook names), and
  component agents may only reach global state through that — otherwise a fan-out of N
  agents invents N private stores.

## Shared VM, not separate VMs

Every agent runs `vm_mode="shared"`: one checkout, no git handoff, and the orchestrator
commits at the end. That is the right trade here because the stages are edits to a single
tree that must typecheck together — passing 11 branches around and merging them would be
most of the work.

It is only safe because **file ownership is disjoint**: each fan-out agent may touch only
the files of its own component and the two it creates. The prompts say so explicitly, and the
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
  first run. Stage 2 deletes the components it ports, so a rescan on resume would return a
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

## Where it still needs a human

Discovery is generic; these are gaps in the *prompts*, and they want a script edit rather
than an env var:

- **Multi-project workspaces / Nx.** One application is migrated — the one `angular.json`
  names first. Libraries the app imports are outside the source root and are not ported.
- **State libraries.** Detected and mapped to Redux Toolkit (above), but never yet run
  against a real NgRx app: the rules are tested for composition, not for their output.
  Read stage 1's `store_api` before letting the fan-out start.
- **i18n and Angular Universal/SSR.** Unhandled.
- **Very large apps.** A 60+ way fan-out contends on one shared VM; batch stage 2.

## Cost and timing

Measured on a small app (11 components, angular2-hn) **without** the reference stage:
**~7 minutes wall clock end to end**, because stage 2's eleven agents run concurrently and
each has one small component to port. Stages 0, 1 and 3 are the long poles. The reference
stage and the screenshot diffing in stage 3 add serial browser time — budget more like
30-45 minutes for the pair, which is the price of a checkable parity claim.

## Failure modes seen in a real run

| Symptom | Cause / fix |
| --- | --- |
| Components each invent their own API client | Stage 1's structured output was vague. Its signatures must be full TypeScript signatures, not prose. |
| A resume starts every agent fresh | The inventory rescanned, or a prompt embeds an unsorted dict. |
| Discovery finds no components | Wrong source root (a workspace whose `angular.json` names a library first). Set `APP_DIR` and delete the cached inventory. |
| Global theme styles stop applying | A component agent CSS-moduled a class that global SCSS targets. Component-scoped styles only; theme class names stay global strings. |
| `npm run build` passes but a route is blank | Stage 3 only checks the routes it knows about. Hand the PR to the testing agent. |
| Input/panel much wider in React than Angular | A `width: %` or `display: block` that ViewEncapsulation used to constrain. Fixed sizing. |
| A modal renders unstyled the first time it opens | Vite injected its CSS on first mount; import that SCSS from an always-mounted parent. |
| Fixing one component's CSS breaks a sibling | Overriding a shared parent selector. Re-check parent/children/siblings after every CSS fix. |
| Error UI never appears for bad input | Some APIs answer HTTP 200 with `{"error": ...}`. The ported fetch wrapper must treat that as a failure — stage 3's prompt says so, but check it. |
| Sass build errors after the theme migration | `@use` module system: `/` division -> `math.div`, `darken()` -> `color.adjust`. |

## Devin Secrets Needed

None.
