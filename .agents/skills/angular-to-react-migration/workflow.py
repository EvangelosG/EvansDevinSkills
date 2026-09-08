"""Dynamic workflow: migrate an Angular application to React + TypeScript + Vite.

Four stages — scaffold, foundation, per-component fan-out, combine — run as shared-VM
subagents against ONE local checkout, so there are no git branch handoffs and the
orchestrator can commit the result itself. Parallelism is safe because every fan-out
agent owns a disjoint set of files (its own component triplet).

Configure with environment variables (see SKILL.md); everything else — the component
inventory, the service/pipe/model list, the routes — is discovered from the checkout.

    REPO_DIR   absolute path to the Angular checkout (required)
    APP_DIR    Angular sources root, relative to REPO_DIR (default: src/app)
"""

import asyncio
import json
import os
import subprocess

REPO_DIR = os.environ.get("REPO_DIR") or os.getcwd()
APP_DIR = os.environ.get("APP_DIR", "src/app")

# The inventory is cached on first run: stage 2 deletes the Angular triplets it ports,
# so re-globbing on a resume would shrink the fan-out and change every prompt hash.
STATE_DIR = os.path.join(
    os.path.expanduser("~"), ".devin-angular-react", os.path.basename(REPO_DIR.rstrip("/"))
)
INVENTORY_PATH = os.path.join(STATE_DIR, "inventory.json")


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True, check=True
    ).stdout.strip()


def _scan_repo():
    """Enumerate the Angular units in the checkout, deterministically (sorted)."""
    app_root = os.path.join(REPO_DIR, APP_DIR)
    components, services, pipes, models, guards = [], [], [], [], []
    for dirpath, _dirnames, filenames in os.walk(app_root):
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), REPO_DIR)
            if name.endswith(".component.ts"):
                components.append(rel[: -len(".ts")])
            elif name.endswith(".service.ts"):
                services.append(rel)
            elif name.endswith(".pipe.ts"):
                pipes.append(rel)
            elif name.endswith(".guard.ts"):
                guards.append(rel)
            elif os.sep + "models" + os.sep in rel and name.endswith(".ts"):
                models.append(rel)
    routes = [
        os.path.relpath(os.path.join(dp, f), REPO_DIR)
        for dp, _dn, fn in os.walk(app_root)
        for f in fn
        if f.endswith(("routes.ts", "-routing.module.ts"))
    ]
    return {
        "components": sorted(components),
        "services": sorted(services),
        "pipes": sorted(pipes),
        "models": sorted(models),
        "guards": sorted(guards),
        "routes": sorted(routes),
    }


def load_inventory():
    if os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH) as fh:
            return json.load(fh)
    inventory = _scan_repo()
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(INVENTORY_PATH, "w") as fh:
        json.dump(inventory, fh, indent=2, sort_keys=True)
    return inventory


BRANCH = _git("rev-parse", "--abbrev-ref", "HEAD")
INVENTORY = load_inventory()
UNITS = INVENTORY["components"]  # e.g. "src/app/core/header/header.component"


def unit_label(base):
    return os.path.basename(base)[: -len(".component")]


META = {
    "name": "angular-to-react",
    "description": "Migrate an Angular application to React + TypeScript on Vite",
    "product": os.path.basename(REPO_DIR.rstrip("/")),
    "soft_time_limit_minutes": 25,
    "phases": [
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
            "detail": "Stage 2: port each Angular component triplet to a React .tsx + .module.scss",
            "count": len(UNITS),
            "labels": [unit_label(u) for u in UNITS],
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
"""

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

FOUNDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "module_paths": {"type": "array", "items": {"type": "string"}},
        "import_specifiers": {"type": "array", "items": {"type": "string"}},
        "exported_signatures": {"type": "array", "items": {"type": "string"}},
        "model_names": {"type": "array", "items": {"type": "string"}},
        "context_hooks": {"type": "array", "items": {"type": "string"}},
        "hook_apis": {"type": "string"},
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
        "summary": {"type": "string"},
    },
    "required": ["build_status", "dev_server_status", "routes_file", "summary"],
}


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
   the matching `@types/*`, plus `sass` if the app uses SCSS and `vite-plugin-pwa` if it
   ships a service worker / manifest. Scripts: `dev`, `build` (tsc --noEmit && vite build),
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


async def stage1_foundation(layout):
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
{json.dumps({k: INVENTORY[k] for k in ("models", "pipes", "services", "guards")}, indent=2, sort_keys=True)}
{TRANSLATION_RULES}
Tasks:
1. Models/interfaces: copy them across unchanged (same names, fields and types).
2. Pipes: convert each to a plain exported utility function, same transformation logic.
3. Stateless services (HTTP/data access): convert to plain modules of async functions
   using fetch + Promises — no RxJS, no Angular DI. Preserve every endpoint, request
   option, aggregation step and error path; throw on failures so callers can render error
   states. Keep the base URL(s) the Angular service used.
4. Stateful services (settings/session/store-like): convert each to a React context +
   provider + `use<Name>()` hook. Preserve localStorage/sessionStorage keys AND their
   stored value formats so existing users keep their state, move browser listeners
   (matchMedia, resize, storage) into useEffect with proper cleanup, and keep every
   action name and state field the service exposed.
5. Guards/resolvers, if any: port to route-level wrapper components or hooks.
6. Wire the providers into the app entry file.
7. Delete the Angular originals you replaced. Leave every *.component.* file and the
   global stylesheet directory untouched — other agents own those.
8. `npx tsc --noEmit`: errors from not-yet-ported components are expected; yours must be clean.

Structured output: the new module paths, the exact import specifiers other agents should
write, the full exported signatures (one string per function, with parameter and return
types), the model names, the context hook names, and `hook_apis`: for each hook, every
state field (name + type) and every action (name + signature).""",
        phase="foundation",
        schema=FOUNDATION_SCHEMA,
        label="foundation",
        vm_mode="shared",
    )


async def stage2_component(base, layout, foundation):
    key = unit_label(base)
    log(f"stage 2: porting {key}")
    return await agent(
        f"""Migrate the Angular application at {REPO_DIR} to React — you are a STAGE 2
component agent. Port exactly ONE Angular component triplet. {len(UNITS) - 1} sibling
agents are porting the other components on this same machine right now, so touching files
outside your assignment corrupts their work.
{COMMON_RULES}
Your unit: `{key}`
Your files (the ONLY files you may create, edit or delete):
  - {base}.ts
  - {base}.html   (may be an inline `template:` in the .ts instead)
  - {base}.scss   (may not exist)
  - the new .tsx and .module.scss you create for it

Layout conventions from stage 0:
{json.dumps(layout, indent=2, sort_keys=True)}

Foundation APIs from stage 1 — import these, never re-implement or guess them:
{json.dumps(foundation, indent=2, sort_keys=True)}
{TRANSLATION_RULES}
Router specifics: replace ActivatedRoute params/data with useParams()/useSearchParams and
Router.navigate with useNavigate(). If the component is the root AppComponent, it becomes
the root App at the app component path above and renders the shell (header/footer/etc.)
plus the router outlet — do NOT write the route table, stage 3 owns it.

Sibling components you may reference by import (being written concurrently, so import at
the conventional path even if the file is not there yet):
{json.dumps(sorted(unit_label(u) for u in UNITS), sort_keys=True)}

Tasks:
1. Read your .ts, .html and .scss.
2. Write a React function component in TypeScript at the conventional path, preserving the
   DOM structure, class names, text and behaviour of the Angular template. Keep loading and
   error states, and any scroll/focus side effects.
3. Move component-scoped SCSS into a co-located *.module.scss; leave global/theme SCSS
   alone (stage 3 migrates it) and keep class names global stylesheets target as plain strings.
4. Delete the original Angular triplet files listed above.
5. Do not run the build or the dev server; stage 3 does. `npx tsc --noEmit` is allowed but
   expect errors from components other agents have not finished.

Structured output: the exported component name, its repo-relative file path, its style file
path, `props_interface` (the full TypeScript prop interface source, or "none"), the sibling
components it renders, and the files you deleted. Stage 3 wires routing and composition
purely from these.""",
        phase="components",
        schema=COMPONENT_SCHEMA,
        label=key,
        vm_mode="shared",
    )


async def stage3_combine(layout, foundation, manifest):
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

Angular route definitions to port (read them from git history if already deleted):
{json.dumps(INVENTORY["routes"], sort_keys=True)}

Tasks:
1. Routing — rebuild the route table with react-router-dom from the Angular routes above:
   same paths, same params, same redirects and wildcard fallback. Angular lazy-loaded
   modules become React.lazy + <Suspense fallback={{...}}>. Wire parent/child composition
   from the manifest and fix prop mismatches between components.
2. Styling — migrate the global/theme stylesheets into the styles dir, imported globally.
   Preserve every theme, applied through a root class driven by the settings context if the
   app has one. Update deprecated Sass (`/` division -> math.div, darken() -> color.adjust)
   as the @use module system requires.
3. PWA — if the Angular app shipped a service worker or manifest, configure vite-plugin-pwa
   to replace ngsw-worker.js: port the manifest and icons, and translate ngsw dataGroups
   into workbox runtimeCaching rules.
4. Deployment/CI — keep the hosting config (firebase.json/netlify.toml/etc.), point its
   publish directory at Vite's `dist` and add the SPA rewrite. Update CI config and README
   to the new npm scripts.
5. Verify — `npm run build` must succeed with no TypeScript errors; then run the dev server
   and check in the browser that each route renders, data loads, and the app's core
   interactions work. Fix whatever fails, including bugs left by earlier agents. Note that
   some APIs return HTTP 200 with an error payload — surface those as errors, not as data.
6. Delete every remaining Angular artifact: leftover *.component.*, *.module.ts,
   main.ts/polyfills.ts/environments, and any Angular dependency still in package.json.
   `grep -ri "@angular" src package.json` must be empty. Stop the dev server before finishing.

Structured output: build_status and dev_server_status ("ok" or the exact failure), the
routes file path, any remaining Angular files you could not remove (with the reason), the
routes you verified, and a summary of what you changed.""",
        phase="combine",
        schema=COMBINE_SCHEMA,
        label="combine",
        vm_mode="shared",
    )


async def main():
    await register_workflow(META)
    log(f"migrating {len(UNITS)} Angular components in {REPO_DIR} on branch {BRANCH}")
    log(f"inventory cached at {INVENTORY_PATH}")

    layout = await stage0_scaffold()
    log(f"stage 0 done: components -> {layout['components_dir']}, routes -> {layout['routes_file']}")

    foundation = await stage1_foundation(layout)
    log(f"stage 1 done: {len(foundation['module_paths'])} foundation modules, hooks: {foundation['context_hooks']}")

    async def run_unit(base):
        try:
            return await stage2_component(base, layout, foundation)
        except WorkflowAgentError as exc:
            log(f"stage 2 FAILED for {unit_label(base)}: {exc}")
            return {
                "component_name": unit_label(base),
                "file_path": "FAILED",
                "props_interface": "unknown",
                "notes": f"agent failed: {exc}; stage 3 must port {base}.* itself",
            }

    manifest = await parallel([(lambda b=b: run_unit(b)) for b in UNITS])
    ported = [m for m in manifest if m["file_path"] != "FAILED"]
    log(f"stage 2 done: {len(ported)}/{len(UNITS)} components ported")

    result = await stage3_combine(layout, foundation, manifest)
    log(f"stage 3 done: build={result['build_status']} dev={result['dev_server_status']}")
    log(json.dumps(result, indent=2, sort_keys=True))


asyncio.run(main())
