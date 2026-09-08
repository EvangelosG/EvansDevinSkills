"""Dynamic workflow: migrate an Angular application to React + TypeScript + Vite.

Five stages — reference, scaffold, foundation, per-component fan-out, combine — run as shared-VM
subagents against ONE local checkout, so there are no git branch handoffs and the
orchestrator can commit the result itself. Parallelism is safe because every fan-out
agent owns a disjoint set of files (its own component's .ts, template and styles).

Nothing about the target app is configured: the source root comes from angular.json and
every unit is classified by the Angular decorator in its source rather than by its
filename, so apps that do not follow the style guide's `*.component.ts` convention
(Angular 20's `header.ts`, Nx libraries, hand-rolled layouts) are discovered the same way.
A state library (NgRx/NGXS/Akita/Elf) is detected the same way, and when one is present the
foundation stage ports it to Redux Toolkit and publishes the hooks and selectors that the
fan-out agents must use — the store is the one contract every component shares.

    REPO_DIR   absolute path to the Angular checkout (default: cwd)
    APP_DIR    override the discovered Angular sources root, relative to REPO_DIR
"""

import asyncio
import json
import os
import re
import subprocess

REPO_DIR = os.environ.get("REPO_DIR") or os.getcwd()

# The inventory is cached on first run: stage 2 deletes the Angular sources it ports,
# so re-globbing on a resume would shrink the fan-out and change every prompt hash.
STATE_DIR = os.path.join(
    os.path.expanduser("~"), ".devin-angular-react", os.path.basename(REPO_DIR.rstrip("/"))
)
INVENTORY_PATH = os.path.join(STATE_DIR, "inventory.json")
# Screenshots of the ORIGINAL Angular app. They live outside the checkout because stage 2
# deletes the Angular sources: after that the reference is unreproducible.
SHOTS_DIR = os.path.join(STATE_DIR, "reference-screenshots")


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True, check=True
    ).stdout.strip()


def _source_root():
    """Where the Angular sources live. angular.json knows; only guess if it does not."""
    override = os.environ.get("APP_DIR")
    if override:
        return override
    cfg_path = os.path.join(REPO_DIR, "angular.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as fh:
            cfg = json.load(fh)
        projects = cfg.get("projects", {})
        candidates = [
            name
            for name in sorted(projects)
            if projects[name].get("projectType", "application") == "application"
        ]
        default = cfg.get("defaultProject")
        if default in candidates:  # multi-project workspace: the app, not the libs
            candidates.insert(0, candidates.pop(candidates.index(default)))
        for name in candidates:
            root = projects[name].get("sourceRoot") or os.path.join(
                projects[name].get("root", ""), "src"
            )
            if os.path.isdir(os.path.join(REPO_DIR, root, "app")):
                return os.path.join(root, "app")
            if os.path.isdir(os.path.join(REPO_DIR, root)):
                return root
    for guess in ("src/app", "src", "app"):
        if os.path.isdir(os.path.join(REPO_DIR, guess)):
            return guess
    raise SystemExit(f"cannot find the Angular sources under {REPO_DIR}; set APP_DIR")


APP_DIR = _source_root()

# Units are classified by their decorator, not their filename: `*.component.ts` is the
# style guide's convention rather than Angular's, and v20 scaffolds plain `header.ts`.
_DECORATOR = re.compile(r"^\s*@(Component|Injectable|Pipe|Directive|NgModule)\s*\(", re.M)
_CLASS = re.compile(r"export\s+(?:abstract\s+)?class\s+(\w+)")
_SELECTOR = re.compile(r"""selector\s*:\s*['"`]([^'"`]+)""")
_TEMPLATE_URL = re.compile(r"""templateUrl\s*:\s*['"`]([^'"`]+)""")
_STYLE_URLS = re.compile(r"""style(?:Urls?)\s*:\s*(\[[^\]]*\]|['"`][^'"`]+['"`])""")
_STRING = re.compile(r"""['"`]([^'"`]+)""")
_GUARD = re.compile(
    r"\b(CanActivate(?:Child|Fn)?|CanMatch(?:Fn)?|CanDeactivate(?:Fn)?|Resolve(?:Fn)?)\b"
)
_ROUTES = re.compile(r":\s*Routes\b|RouterModule\.for(?:Root|Child)\s*\(")
# A model is any decorator-free file that only declares shapes — including the plain
# `export class Story {}` style, which is a data class in Angular apps, not a service.
_TYPES_ONLY = re.compile(r"export\s+(?:interface|type|enum|class)\b")
_ANGULAR_IMPORT = re.compile(r"""from\s+['"]@angular/""")
# A store is the one Angular pattern that spans every component, so it has to be found
# before the fan-out and ported behind a published API like the services are.
_STATE_LIBS = {
    "ngrx": re.compile(r"""from\s+['"]@ngrx/"""),
    "ngxs": re.compile(r"""from\s+['"]@ngxs/"""),
    "akita": re.compile(r"""from\s+['"]@datorama/akita"""),
    "elf": re.compile(r"""from\s+['"]@ngneat/elf"""),
}


def _rel(path):
    return os.path.relpath(path, REPO_DIR)


def _resolve(base_dir, ref):
    candidate = os.path.normpath(os.path.join(base_dir, ref))
    return _rel(candidate) if os.path.exists(candidate) else None


def _describe_component(path, text):
    """A component owns its .ts plus whatever templateUrl/styleUrls actually point at."""
    here = os.path.dirname(path)
    template_ref = _TEMPLATE_URL.search(text)
    styles_ref = _STYLE_URLS.search(text)
    styles = []
    if styles_ref:
        styles = [
            resolved
            for ref in _STRING.findall(styles_ref.group(1))
            for resolved in [_resolve(here, ref)]
            if resolved
        ]
    class_match = _CLASS.search(text)
    selector = _SELECTOR.search(text)
    return {
        "class_name": class_match.group(1) if class_match else os.path.basename(path)[:-3],
        "selector": selector.group(1) if selector else "",
        "ts": _rel(path),
        "template": (_resolve(here, template_ref.group(1)) or "missing")
        if template_ref
        else "inline",
        "styles": sorted(styles),
    }


def _label_for(component):
    """`HeaderComponent` -> `header`; uniqueness is enforced by the caller."""
    name = re.sub(r"Component$", "", component["class_name"])
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
    return kebab or os.path.basename(component["ts"])[:-3]


def _scan_repo():
    """Enumerate the Angular units in the checkout, deterministically (sorted)."""
    app_root = os.path.join(REPO_DIR, APP_DIR)
    found = {
        key: []
        for key in ("components", "services", "pipes", "directives", "modules", "guards",
                    "models", "routes", "other", "store")
    }
    state_libs = set()
    for dirpath, dirnames, filenames in os.walk(app_root):
        dirnames[:] = sorted(d for d in dirnames if d not in ("node_modules", "dist"))
        for name in sorted(filenames):
            if not name.endswith(".ts") or name.endswith((".spec.ts", ".d.ts")):
                continue
            path = os.path.join(dirpath, name)
            with open(path, errors="replace") as fh:
                text = fh.read()
            decorator = _DECORATOR.search(text)
            kind = decorator.group(1) if decorator else None
            libraries = [lib for lib, pat in _STATE_LIBS.items() if pat.search(text)]
            if libraries:
                # NGXS/Akita state carries its own decorators, so it would otherwise land
                # in `models` and be "copied across unchanged" — it has to be ported.
                state_libs.update(libraries)
                found["store"].append(_rel(path))
            if kind == "Component":
                found["components"].append(_describe_component(path, text))
            elif kind == "Injectable":
                # Guards and resolvers are @Injectable too; what they implement decides.
                target = "guards" if _GUARD.search(text) else "services"
                found[target].append(_rel(path))
            elif kind == "Pipe":
                found["pipes"].append(_rel(path))
            elif kind == "Directive":
                found["directives"].append(_rel(path))
            elif kind == "NgModule":
                found["modules"].append(_rel(path))
            elif _GUARD.search(text):
                found["guards"].append(_rel(path))  # functional guard, no decorator
            elif libraries:
                pass  # already recorded under `store`
            elif _TYPES_ONLY.search(text) and not _ANGULAR_IMPORT.search(text):
                found["models"].append(_rel(path))
            elif not kind and not _ROUTES.search(text):
                found["other"].append(_rel(path))  # environments, tokens, helpers
            if _ROUTES.search(text):
                found["routes"].append(_rel(path))

    components = sorted(found.pop("components"), key=lambda c: c["ts"])
    # Labels name the fan-out agents, so they have to be unique. Two components can share a
    # class name across feature folders (admin/list vs list), so collisions take the folder.
    base = [_label_for(component) for component in components]
    labels, taken = [], {}
    for component, label in zip(components, base):
        if base.count(label) > 1:
            parts = [p for p in os.path.dirname(component["ts"]).split(os.sep) if p != label]
            if parts:
                label = f"{parts[-1]}-{label}"
        taken[label] = taken.get(label, 0) + 1
        labels.append(label if taken[label] == 1 else f"{label}-{taken[label]}")
    for component, label in zip(components, labels):
        component["label"] = label
    inventory = {
        "source_root": APP_DIR,
        "components": components,
        **{key: sorted(set(value)) for key, value in found.items()},
    }
    inventory["state_libraries"] = sorted(state_libs)
    return inventory


def load_inventory():
    if os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH) as fh:
            return json.load(fh)
    inventory = _scan_repo()
    if not inventory["components"]:
        raise SystemExit(f"no @Component classes found under {APP_DIR}; wrong APP_DIR?")
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(INVENTORY_PATH, "w") as fh:
        json.dump(inventory, fh, indent=2, sort_keys=True)
    return inventory


BRANCH = _git("rev-parse", "--abbrev-ref", "HEAD")
INVENTORY = load_inventory()
UNITS = INVENTORY["components"]  # dicts: class_name, label, ts, template, styles, selector


META = {
    "name": "angular-to-react",
    "description": "Migrate an Angular application to React + TypeScript on Vite",
    "product": os.path.basename(REPO_DIR.rstrip("/")),
    "soft_time_limit_minutes": 25,
    "phases": [
        {
            "title": "reference",
            "detail": "Stage -1: run the Angular app and screenshot every route/state as the visual spec",
            "count": 1,
            "labels": ["reference"],
            "soft_time_limit_minutes": 45,
        },
        {
            "title": "scaffold",
            "detail": "Stage 0: scaffold React+Vite, purge Angular config/tooling, publish the src/ layout",
            "count": 1,
            "labels": ["scaffold"],
            "soft_time_limit_minutes": 30,
        },
        {
            "title": "foundation",
            "detail": "Stage 1: port models, pipes, services and stateful services -> context/hooks",
            "count": 1,
            "labels": ["foundation"],
            "soft_time_limit_minutes": 30,
        },
        {
            "title": "components",
            "detail": "Stage 2: port each discovered @Component to a React .tsx + .module.scss",
            "count": len(UNITS),
            "labels": [u["label"] for u in UNITS],
            "soft_time_limit_minutes": 25,
        },
        {
            "title": "combine",
            "detail": "Stage 3: routing, styling, PWA, deployment config, build + browser verification",
            "count": 1,
            "labels": ["combine"],
            "soft_time_limit_minutes": 60,
        },
    ],
}

COMMON_RULES = f"""
Repository checkout: {REPO_DIR} (already on branch `{BRANCH}`).
You are one agent in a multi-stage Angular -> React migration. Other agents run on this
same machine against this same working tree at the same time.

Hard rules:
- Do NOT run any state-changing git command (no checkout/switch/branch/commit/push/
  stash/reset/clean). The orchestrator commits. `git status`/`git diff`/`git log` are fine.
- Only create, edit or delete the files your task assigns you. Other agents own the rest.
- Do NOT run `npm install`/`npm ci` and do NOT start a dev server unless your task says
  to. Do not kill processes you did not start.
- Feature parity is the whole job: no new features, no new UI, no extra dependencies, no
  "modernising" (no Tailwind/CSS-in-JS/state library) beyond what the task lists.
- Use the repo's Node toolchain (if the repo uses nvm: `source ~/.nvm/nvm.sh && nvm use`).
- Read the original Angular sources before porting; preserve behaviour and markup.
- Finish by calling provide_structured_output with the requested fields.
"""

TRANSLATION_RULES = """
Angular -> React translation rules (apply consistently):
- *ngIf -> conditional rendering; *ngFor -> .map() with a stable key
- [prop]="x" -> prop={x}; (event)="f()" -> onEvent={f}
- routerLink -> <Link to=...> from react-router-dom
- async pipe -> resolved state from useState/useEffect
- @Input() -> props; @Output() EventEmitter -> callback props
- ngOnInit / ngOnDestroy -> useEffect (with a cleanup return)
- ngOnChanges -> useEffect keyed on the relevant props
- class/[ngClass] -> className with the CSS-module class; class names that global theme
  stylesheets target must stay plain global strings
- template pipes -> plain helper function calls
- Observables/RxJS in services -> async functions returning Promises
- injected stateful services -> React context + a use<Name>() hook
- <ng-content> -> the children prop; each <ng-content select="x"> -> its own ReactNode prop
- @ViewChild/@ViewChildren -> useRef for DOM access; if Angular called a child's method,
  lift the state up or pass a callback prop instead of imperative calls
- @HostListener -> a JSX handler, or addEventListener in useEffect with cleanup
- @HostBinding -> className/style on the component's root element
- @angular/animations -> CSS transitions/keyframes toggled by a state boolean
- template-driven/reactive forms -> controlled inputs with useState + onChange

Correctness rules that Angular gave you for free and React does not:
- Every fetch must check `if (!res.ok) throw` BEFORE res.json(), and must treat an HTTP 200
  body that carries an error field as a failure. Otherwise error states never render.
- Every useEffect that fetches must ignore stale responses:
  `let cancelled = false; ...; if (!cancelled) setX(v); return () => { cancelled = true; }`
  Without it, switching route params fast renders the older response.
- Persisted state (localStorage/sessionStorage/cookies) must be read in the useState
  initialiser, never in a useEffect — reading it later flashes the default value first.
- dangerouslySetInnerHTML must go through DOMPurify.sanitize(); Angular sanitised bindings
  by default, React does not.
- Never nest <Link> inside <a> (or vice versa). An <a [routerLink] class=...> becomes
  <Link to=... className=...> with the attributes moved onto the Link.
"""

# Angular's ViewEncapsulation silently scoped every component stylesheet; importing SCSS in
# React does not. This is the single largest source of post-migration bugs.
CSS_RULES = """
CSS scoping rules (Angular ViewEncapsulation has no React equivalent — read carefully):
- Never leave a bare element selector (a, h1, p, li, ul, input, button) at the top level of
  a component stylesheet. Every rule is nested under the component's own wrapper class (or
  lives in a *.module.scss), and that wrapper class is on the component's root element.
- Use direct child combinators (`.wrapper > .nav a`) where a component renders child
  components, so the parent's selectors cannot match elements inside its children.
- Check the component that RENDERS yours: its element selectors match your elements too
  (a Settings dialog inside a Header inherits `.header h1 {}`). Make the offending selector
  specific to the parent's own elements rather than loosening yours.
- Global/theme stylesheets outrank component class selectors when they nest element
  selectors under a theme class (`.night .wrapper a { color: ... }`). Where your component
  needs different values, beat them with an id selector or !important, and set :visited
  explicitly — otherwise visited links fall back to browser purple.
- Percentage widths and `display: block` measured against the encapsulated component in
  Angular now measure against the full parent; use fixed sizing where the element grows.
- Drop :host, :host-context, /deep/ and >>>; fold what they did into the wrapper class.
- A component rendered conditionally (modal/drawer/popup) only gets its CSS injected when it
  first mounts under Vite. Import its stylesheet from a component that is always mounted.
"""

# Only apps that actually have a store pay for these rules; for everything else the block is
# empty, which also keeps those prompts (and their cached results) unchanged.
STATE_LIBRARIES = INVENTORY["state_libraries"]
STORE_RULES = (
    ""
    if not STATE_LIBRARIES
    else f"""
This app keeps global state in {", ".join(STATE_LIBRARIES)} ({len(INVENTORY["store"])} files,
listed in the inventory). Port it to Redux Toolkit + react-redux, because that is the
library whose shape (a single typed store, reducers keyed by action, selectors, thunks for
side effects) maps one-to-one onto what is already there:
- one feature slice per reducer/state class: `createSlice({{ name, initialState, reducers }})`,
  with the SAME state field names, so selectors and templates keep meaning
- actions -> the slice's generated action creators; keep the action names recognisable
- selectors -> `createSelector` in the slice file, exported one per Angular selector
- effects (@ngrx/effects, NGXS @Action doing async work) -> `createAsyncThunk`, with the
  pending/fulfilled/rejected cases handled in `extraReducers` where the effect dispatched
  success/failure actions. Do NOT collapse an effect into a component useEffect: the point
  of the barrier is that components share one store, not N private fetches.
- `store.select(x) | async` in a template -> `useAppSelector(x)`
- `store.dispatch(a)` -> `useAppDispatch()`
- export typed hooks (`useAppSelector`/`useAppDispatch` bound to RootState/AppDispatch) and
  wrap the app in <Provider store={{store}}> — component agents may only use those hooks.
Entity adapters, meta-reducers and router-store have no React equivalent worth emulating:
replace an entity adapter with plain normalised state, and drop router-store in favour of
useParams/useLocation. Report anything you drop.
"""
)

SCAFFOLD_SCHEMA = {
    "type": "object",
    "properties": {
        "components_dir": {"type": "string"},
        "services_dir": {"type": "string"},
        "context_dir": {"type": "string"},
        "models_dir": {"type": "string"},
        "styles_dir": {"type": "string"},
        "routes_file": {"type": "string"},
        "entry_file": {"type": "string"},
        "app_component_path": {"type": "string"},
        "conventions": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": [
        "components_dir",
        "services_dir",
        "context_dir",
        "models_dir",
        "styles_dir",
        "routes_file",
        "entry_file",
        "app_component_path",
        "conventions",
    ],
}

REFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "screenshots": {"type": "array", "items": {"type": "string"}},
        "routes_walked": {"type": "array", "items": {"type": "string"}},
        "ui_states": {"type": "array", "items": {"type": "string"}},
        "behaviour_notes": {"type": "string"},
        "global_style_hazards": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": [
        "screenshots",
        "routes_walked",
        "ui_states",
        "behaviour_notes",
        "global_style_hazards",
    ],
}

FOUNDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "module_paths": {"type": "array", "items": {"type": "string"}},
        "import_specifiers": {"type": "array", "items": {"type": "string"}},
        "exported_signatures": {"type": "array", "items": {"type": "string"}},
        "model_names": {"type": "array", "items": {"type": "string"}},
        "context_hooks": {"type": "array", "items": {"type": "string"}},
        "hook_apis": {"type": "string"},
        # "" when the app has no store; otherwise the contract stage 2 codes against.
        "store_api": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": [
        "module_paths",
        "import_specifiers",
        "exported_signatures",
        "model_names",
        "context_hooks",
        "hook_apis",
    ],
}

COMPONENT_SCHEMA = {
    "type": "object",
    "properties": {
        "component_name": {"type": "string"},
        "file_path": {"type": "string"},
        "style_path": {"type": "string"},
        "props_interface": {"type": "string"},
        "children_used": {"type": "array", "items": {"type": "string"}},
        "style_scope_class": {"type": "string"},
        "deleted_files": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["component_name", "file_path", "props_interface"],
}

COMBINE_SCHEMA = {
    "type": "object",
    "properties": {
        "build_status": {"type": "string"},
        "dev_server_status": {"type": "string"},
        "routes_file": {"type": "string"},
        "remaining_angular_files": {"type": "array", "items": {"type": "string"}},
        "verified_routes": {"type": "array", "items": {"type": "string"}},
        "screenshot_diffs": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["build_status", "dev_server_status", "routes_file", "summary"],
}


async def stage_ref_capture():
    log("stage -1: capturing the Angular app's reference screenshots")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are the REFERENCE stage,
and you run BEFORE anything is changed. Later stages delete the Angular sources, so the
running original can never be seen again after you. Your screenshots are the acceptance
criteria the final stage diffs the React app against.
{COMMON_RULES}
(You are allowed to `npm install` the Angular dependencies and to run the Angular dev
server, because the app must run to be photographed. Change NO source file.)

Angular inventory discovered in the checkout:
{json.dumps(INVENTORY, indent=2, sort_keys=True)}

Tasks:
1. Install dependencies and serve the app locally (`ng serve` / the repo's start script).
   Do not use a hosted copy of the app; it must be this checkout. If the build fails on a
   modern Node, use the Node version the repo pins.
2. Read the route definitions and walk EVERY route in the browser, plus every distinct UI
   state you can reach: each nav/feed/tab, a detail page, pagination, modals and dropdowns
   open, every theme, and the error/empty/loading states (an invalid id or a blocked
   request will produce them).
3. Screenshot each one full-window into {SHOTS_DIR}/ with descriptive names
   (`news-page.png`, `settings-modal-open.png`, `night-theme.png`, `item-error.png`).
   One file per state — a recording is not a substitute, individual frames are what the
   final stage compares against.
4. Note behaviour a screenshot cannot show: what persists across reload, what refetches on
   navigation, scroll/focus side effects, link targets, analytics/pageview hooks.
5. Grep the global and theme stylesheets for bare element selectors nested under theme or
   layout classes (`a`, `h1`, `p`, `li`) and record them as `global_style_hazards`: these
   outrank component class selectors and are injected into every component agent's prompt.
6. Stop the dev server before you finish. Leave the working tree exactly as you found it
   (`git status` clean apart from untracked node_modules).

Structured output: absolute screenshot paths, the routes walked, the UI states captured,
the behaviour notes, and the global style hazards.""",
        phase="reference",
        schema=REFERENCE_SCHEMA,
        label="reference",
        vm_mode="shared",
    )


async def stage0_scaffold():
    log("stage 0: scaffolding React + Vite project")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are STAGE 0 (scaffold).
Later agents port the foundation modules, the components and the routing, so your only
job is a consistent React + TypeScript + Vite base plus the src/ layout conventions
every later agent must follow.
{COMMON_RULES}
Angular inventory discovered in the checkout:
{json.dumps(INVENTORY, indent=2, sort_keys=True)}

Tasks:
1. Scaffold a React + TypeScript app with Vite in place (keep the existing repo root; no
   nested project directory). index.html at the repo root referencing /src/main.tsx.
2. Rewrite package.json: remove every `@angular/*`, `rxjs`, `zone.js`, `codelyzer`,
   `karma*`, `protractor`, `jasmine*`, `tslint`, `ts-node` and Angular CLI package; add
   `react`, `react-dom`, `react-router-dom`, `typescript`, `vite`, `@vitejs/plugin-react`,
   the matching `@types/*`, plus `sass` if the app uses SCSS, `vite-plugin-pwa` if it
   ships a service worker / manifest, `dompurify` + `@types/dompurify` if any template
   binds raw HTML ([innerHTML]), and `@reduxjs/toolkit` + `react-redux` if the inventory
   reports a state library. Scripts: `dev`, `build` (tsc --noEmit && vite build),
   `preview`, and `lint`. Use versions published well before today; never `latest`/`*`.
3. Delete Angular config: angular.json, tsconfig.app.json, tsconfig.spec.json, tslint.json,
   karma.conf.js, ngsw-config.json, webpack.config.js, the Protractor `e2e/` suite, and
   `browserslist` if only Angular used it. Add vite.config.ts and a React-JSX tsconfig.json
   (jsx: react-jsx, strict, moduleResolution bundler).
4. Run `npm install` (you are the ONLY agent allowed to install) and confirm `npx tsc
   --noEmit` runs.
5. Create the directory skeleton for the layout you choose and write src/main.tsx
   bootstrapping <App/> inside <BrowserRouter>. A placeholder App is fine — a later agent
   overwrites it at the path you report.
6. Port NOTHING from {APP_DIR}: no component, service, pipe, model or SCSS content.

Report the layout conventions: directories for components, services, context, models and
styles, the routes file path, the entry file, where the root App component must live, and
a `conventions` string describing naming (PascalCase .tsx, co-located *.module.scss,
import alias or relative imports) precisely enough that {len(UNITS)} independent agents
write mutually consistent code.""",
        phase="scaffold",
        schema=SCAFFOLD_SCHEMA,
        label="scaffold",
        vm_mode="shared",
    )


async def stage1_foundation(layout, reference):
    log("stage 1: porting models, pipes, services and stateful services")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are STAGE 1
(foundation). The React + Vite scaffold exists. You port the shared dependencies every
component agent imports next; the signatures you report are injected verbatim into their
prompts, so they must be exact.
{COMMON_RULES}
Layout conventions from stage 0 (follow exactly):
{json.dumps(layout, indent=2, sort_keys=True)}

Angular sources you own (and only these):
{json.dumps({k: INVENTORY[k] for k in ("models", "pipes", "services", "guards", "directives", "other", "store")}, indent=2, sort_keys=True)}
(Classified by decorator: `services` are @Injectable, `guards` implement CanActivate/
CanMatch/Resolve, `models` are decorator-free shape-only files, `other` is everything left
over — tokens, constants, helpers — which you port only if a component will need it.
NgModules and route files belong to stage 3.)

Observed behaviour of the original app (from the reference stage) — your ported modules
must reproduce it, especially what survives a reload:
{json.dumps({k: reference[k] for k in ("behaviour_notes", "ui_states")}, indent=2, sort_keys=True)}
{TRANSLATION_RULES}{STORE_RULES}
Tasks:
1. Models/interfaces: copy them across unchanged (same names, fields and types).
2. Pipes: convert each to a plain exported utility function, same transformation logic.
3. Stateless services (HTTP/data access): convert to plain modules of async functions
   using fetch + Promises — no RxJS, no Angular DI. Preserve every endpoint, request
   option, aggregation step and error path; throw on failures so callers can render error
   states. Keep the base URL(s) the Angular service used.
4. Stateful services (settings/session/store-like): convert each to a React context +
   provider + `use<Name>()` hook. Preserve localStorage/sessionStorage keys AND their
   stored value formats so existing users keep their state, read every persisted value in
   the useState initialiser (not in a useEffect), move browser listeners (matchMedia,
   resize, storage) into useEffect with proper cleanup, and keep every action name and
   state field the service exposed.
5. Guards/resolvers, if any: port to route-level wrapper components or hooks. Attribute
   directives become a hook or a wrapper component with the same behaviour. HttpInterceptors
   become the shared fetch wrapper (auth header injection, central error handling, loading
   flags) — one wrapper the data modules call, not logic copied per call site.
6. If any template binds raw HTML, export a `sanitizeHtml` helper wrapping DOMPurify for the
   component agents to use. Report every helper you add under `module_paths`.
   The `store` files, if the inventory lists any, are yours too: port them per the state
   rules above and report the result under `store_api` — slice names, state shape, every
   selector and action creator, and the typed hook names. Component agents get that string
   verbatim and may not reach into the store any other way.
7. Wire the providers into the app entry file.
8. Delete the Angular originals you replaced. Leave every file listed in the component
   inventory and the global stylesheet directory untouched — other agents own those.
9. `npx tsc --noEmit`: errors from not-yet-ported components are expected; yours must be clean.

Structured output: the new module paths, the exact import specifiers other agents should
write, the full exported signatures (one string per function, with parameter and return
types), the model names, the context hook names, and `hook_apis`: for each hook, every
state field (name + type) and every action (name + signature).""",
        phase="foundation",
        schema=FOUNDATION_SCHEMA,
        label="foundation",
        vm_mode="shared",
    )


async def stage2_component(unit, layout, foundation, reference):
    key = unit["label"]
    owned = "\n".join(
        f"  - {path}"
        for path in [unit["ts"], *unit["styles"]]
        + ([unit["template"]] if unit["template"] not in ("inline", "missing") else [])
    )
    log(f"stage 2: porting {key}")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are a STAGE 2
component agent. Port exactly ONE Angular component. {len(UNITS) - 1} sibling
agents are porting the other components on this same machine right now, so touching files
outside your assignment corrupts their work.
{COMMON_RULES}
Your unit: `{key}` (class `{unit["class_name"]}`, selector `{unit["selector"] or "none"}`)
Your files (the ONLY files you may create, edit or delete):
{owned}
  - the new .tsx and .module.scss you create for it
{"(the template is inline in the .ts)" if unit["template"] == "inline" else ""}

Layout conventions from stage 0:
{json.dumps(layout, indent=2, sort_keys=True)}

Foundation APIs from stage 1 — import these, never re-implement or guess them (including
`store_api`, if present: it is the only way into global state):
{json.dumps(foundation, indent=2, sort_keys=True)}

Reference screenshots of the ORIGINAL app are in {SHOTS_DIR}. Open the ones showing your
component and match them: same layout, spacing, weights and colours. The Angular app is
already deleted/being deleted, so these images are the only spec.

Global stylesheet selectors that will fight your component's styles:
{json.dumps(reference["global_style_hazards"], sort_keys=True)}
{TRANSLATION_RULES}{STORE_RULES}
{CSS_RULES}
Router specifics: replace ActivatedRoute params/data with useParams()/useSearchParams and
Router.navigate with useNavigate(). If the component is the root AppComponent, it becomes
the root App at the app component path above and renders the shell (header/footer/etc.)
plus the router outlet — do NOT write the route table, stage 3 owns it.

Sibling components you may reference by import (Angular selector -> the label of the agent
porting it; they are being written concurrently, so import at the conventional path even if
the file is not there yet):
{json.dumps({u["selector"] or u["label"]: u["label"] for u in UNITS}, indent=2, sort_keys=True)}

Tasks:
1. Read the files listed above.
2. Write a React function component in TypeScript at the conventional path, preserving the
   DOM structure, class names, text and behaviour of the Angular template. Keep loading and
   error states, and any scroll/focus side effects.
3. Move component-scoped SCSS into a co-located *.module.scss, applying the CSS scoping
   rules above to every rule you copy — scope them as you write them, never "scope later".
   Leave global/theme SCSS alone (stage 3 migrates it) and keep class names that global
   stylesheets target as plain global strings.
4. Compare your rendered markup against the reference screenshots and fix differences now;
   the later a scoping bug is found, the harder it is to attribute.
5. Delete the original Angular files listed above.
6. Do not run the build or the dev server; stage 3 does. `npx tsc --noEmit` is allowed but
   expect errors from components other agents have not finished.

Structured output: the exported component name, its repo-relative file path, its style file
path, `props_interface` (the full TypeScript prop interface source, or "none"), the sibling
components it renders, `style_scope_class` (the wrapper/module class its rules are nested
under), and the files you deleted. Stage 3 wires routing and composition
purely from these.""",
        phase="components",
        schema=COMPONENT_SCHEMA,
        label=key,
        vm_mode="shared",
    )


async def stage3_combine(layout, foundation, manifest, reference):
    log("stage 3: routing, styles, PWA, deployment and verification")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are STAGE 3 (combine).
The scaffold, the foundation modules and all {len(UNITS)} React components are in the
working tree. You own everything that remains and you are the only agent running now, so
you may touch any file and run the build and the dev server.
{COMMON_RULES}
(The "only your own files" rule is lifted for you; the git rule still applies.)

Layout conventions from stage 0:
{json.dumps(layout, indent=2, sort_keys=True)}

Foundation APIs from stage 1:
{json.dumps(foundation, indent=2, sort_keys=True)}

Component manifest from stage 2:
{json.dumps(manifest, indent=2, sort_keys=True)}

Reference stage output — screenshots of the original Angular app in {SHOTS_DIR}, the routes
and states it walked, and the behaviour it recorded:
{json.dumps(reference, indent=2, sort_keys=True)}
{CSS_RULES}

Angular route definitions to port, and the NgModules whose declarations/providers/
loadChildren describe the app's composition (read them from git history if already
deleted):
{json.dumps({k: INVENTORY[k] for k in ("routes", "modules")}, indent=2, sort_keys=True)}

Tasks:
0. If stage 1 reported a `store_api`, wire <Provider store={{store}}> into the entry file
   above the router and check that no component fetched around the store.
1. Routing — rebuild the route table with react-router-dom from the Angular routes above:
   same paths, same params, same redirects and wildcard fallback. Angular lazy-loaded
   modules become React.lazy + <Suspense fallback={{...}}>. Wire parent/child composition
   from the manifest and fix prop mismatches between components. If the Angular app tracked
   pageviews off Router events, reimplement it with useLocation + useEffect — and skip the
   first render with a useRef if `/` redirects, since NavigationEnd did not fire there and
   counting it would double-count the redirect target.
2. Styling — migrate the global/theme stylesheets into the styles dir, imported globally.
   Preserve every theme, applied through a root class driven by the settings context if the
   app has one. Update deprecated Sass (`/` division -> math.div, darken() -> color.adjust)
   as the @use module system requires. Import the stylesheet of every conditionally rendered
   component (modals, drawers) from an always-mounted parent so its CSS exists before it
   first opens.
3. PWA — if the Angular app shipped a service worker or manifest, configure vite-plugin-pwa
   to replace ngsw-worker.js: port the manifest and icons, and translate ngsw dataGroups
   into workbox runtimeCaching rules.
4. Deployment/CI — keep the hosting config (firebase.json/netlify.toml/etc.), point its
   publish directory at Vite's `dist` and add the SPA rewrite. Update CI config and README
   to the new npm scripts.
5. Verify — `npm run build` must succeed with no TypeScript errors; then run the dev server
   and go through the reference screenshots ONE BY ONE: navigate to the same route/state,
   screenshot the React app, open both images and compare layout, sizing, spacing, colour,
   font weight and link states. Fix each discrepancy before moving to the next image, then
   re-shoot to confirm. Because CSS fixes cascade, after each fix re-check the neighbouring
   components (parent, children, siblings) for regressions. Also verify the behaviour the
   reference stage recorded: persistence across reload, refetch on navigation, error states.
   Fix whatever fails, including bugs left by earlier agents. Note that some APIs return
   HTTP 200 with an error payload — surface those as errors, not as data. With a store,
   walk the flows that dispatch: the state each one produces, the async success/failure
   paths the effects covered, and whether the state survives reload where it did before.
6. Delete every remaining Angular artifact: whatever is left under {APP_DIR}, the NgModules
   above, main.ts/polyfills.ts/environments, and any Angular dependency in package.json.
   `grep -riE "@angular|@ngrx|@ngxs" src package.json` must be empty. Stop the dev server
   before finishing.

Structured output: build_status and dev_server_status ("ok" or the exact failure), the
routes file path, any remaining Angular files you could not remove (with the reason), the
routes you verified, `screenshot_diffs` (one entry per reference screenshot: its name, and
either "match" or the difference you could not resolve), and a summary of what you changed.""",
        phase="combine",
        schema=COMBINE_SCHEMA,
        label="combine",
        vm_mode="shared",
    )


async def main():
    await register_workflow(META)
    log(f"migrating {len(UNITS)} Angular components in {REPO_DIR} on branch {BRANCH}")
    log(f"inventory cached at {INVENTORY_PATH}")

    reference = await stage_ref_capture()
    log(f"reference done: {len(reference['screenshots'])} screenshots in {SHOTS_DIR}")

    layout = await stage0_scaffold()
    log(f"stage 0 done: components -> {layout['components_dir']}, routes -> {layout['routes_file']}")

    foundation = await stage1_foundation(layout, reference)
    log(f"stage 1 done: {len(foundation['module_paths'])} foundation modules, hooks: {foundation['context_hooks']}")

    async def run_unit(base):
        try:
            return await stage2_component(base, layout, foundation, reference)
        except WorkflowAgentError as exc:
            log(f"stage 2 FAILED for {base['label']}: {exc}")
            return {
                "component_name": base["label"],
                "file_path": "FAILED",
                "props_interface": "unknown",
                "notes": f"agent failed: {exc}; stage 3 must port {base['ts']} itself",
            }

    manifest = await parallel([(lambda b=b: run_unit(b)) for b in UNITS])
    ported = [m for m in manifest if m["file_path"] != "FAILED"]
    log(f"stage 2 done: {len(ported)}/{len(UNITS)} components ported")

    result = await stage3_combine(layout, foundation, manifest, reference)
    log(f"stage 3 done: build={result['build_status']} dev={result['dev_server_status']}")
    log(json.dumps(result, indent=2, sort_keys=True))


asyncio.run(main())
