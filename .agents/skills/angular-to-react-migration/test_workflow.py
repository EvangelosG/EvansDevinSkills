"""Tests for workflow.py's discovery and prompt composition: `python3 -m unittest discover`.

The workflow only runs inside a dynamic-workflow session, where `agent`, `parallel`,
`register_workflow`, `log` and `WorkflowAgentError` are injected builtins. Here it is
exec'd against stubs that answer every agent call from its own JSON schema, so a whole run
completes offline and every prompt it would have sent is captured for assertion.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import textwrap
import unittest

WORKFLOW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow.py")

COMPONENT = """
import {{ Component }} from '@angular/core';

@Component({{
  selector: '{selector}',
  templateUrl: './{stem}.html',
  styleUrls: ['./{stem}.scss'],
}})
export class {cls} {{}}
"""


def init_repo():
    """A checkout with a HEAD: the workflow reads the current branch on startup."""
    root = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init",
         "--allow-empty"],
        cwd=root,
        check=True,
    )
    return root


def write(root, files):
    for rel, body in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(textwrap.dedent(body))


def component(root, directory, stem, cls, selector):
    write(
        root,
        {
            f"{directory}/{stem}.ts": COMPONENT.format(stem=stem, cls=cls, selector=selector),
            f"{directory}/{stem}.html": "<div></div>",
            f"{directory}/{stem}.scss": "a { color: red; }",
        },
    )


def _stub_result(schema):
    """Answer an agent call from its schema, so main() can read any field it declares."""
    return {
        name: [] if spec["type"] == "array" else "stub"
        for name, spec in schema["properties"].items()
    }


def run_workflow(repo_dir):
    """Execute the workflow end to end against stub agents; return (module, prompts)."""
    prompts = {}

    async def agent(prompt, phase, schema, label, vm_mode):
        prompts[label] = prompt
        return _stub_result(schema)

    async def parallel(calls):
        return await asyncio.gather(*(call() for call in calls))

    namespace = {
        "__name__": "workflow_under_test",
        "agent": agent,
        "parallel": parallel,
        "register_workflow": lambda meta: asyncio.sleep(0),
        "log": lambda *args: None,
        "WorkflowAgentError": RuntimeError,
    }
    with tempfile.TemporaryDirectory() as home:  # isolate the inventory cache per test
        env = dict(os.environ, HOME=home, REPO_DIR=repo_dir)
        env.pop("APP_DIR", None)
        original, os.environ = os.environ, env
        try:
            with open(WORKFLOW) as fh:
                exec(compile(fh.read(), WORKFLOW, "exec"), namespace)
        finally:
            os.environ = original
    return namespace, prompts


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()

    def scan(self):
        namespace, prompts = run_workflow(self.repo)
        return namespace["INVENTORY"], prompts

    def test_classifies_by_decorator_not_filename(self):
        """Angular 20 scaffolds `header.ts`; the style guide's suffixes are a convention."""
        component(self.repo, "src/app/header", "header", "HeaderComponent", "app-header")
        write(
            self.repo,
            {
                "src/app/core/api.ts": """
                    import { Injectable } from '@angular/core';
                    @Injectable({ providedIn: 'root' })
                    export class ApiService {}
                """,
                "src/app/core/time.ts": """
                    import { Pipe, PipeTransform } from '@angular/core';
                    @Pipe({ name: 'time' })
                    export class TimePipe implements PipeTransform { transform() {} }
                """,
                "src/app/core/highlight.ts": """
                    import { Directive } from '@angular/core';
                    @Directive({ selector: '[highlight]' })
                    export class HighlightDirective {}
                """,
                "src/app/core/auth.ts": """
                    export const authGuard: CanActivateFn = () => true;
                """,
                "src/app/models/story.ts": "export interface Story { id: number; }",
                "src/app/app.routes.ts": """
                    export const routes: Routes = [{ path: '', component: HeaderComponent }];
                """,
                "src/app/header/header.spec.ts": "describe('HeaderComponent', () => {});",
            },
        )
        inventory, _ = self.scan()

        self.assertEqual([c["label"] for c in inventory["components"]], ["header"])
        self.assertEqual(inventory["services"], ["src/app/core/api.ts"])
        self.assertEqual(inventory["pipes"], ["src/app/core/time.ts"])
        self.assertEqual(inventory["directives"], ["src/app/core/highlight.ts"])
        self.assertEqual(inventory["guards"], ["src/app/core/auth.ts"])
        self.assertEqual(inventory["models"], ["src/app/models/story.ts"])
        self.assertEqual(inventory["routes"], ["src/app/app.routes.ts"])
        self.assertNotIn("src/app/header/header.spec.ts", json.dumps(inventory))

    def test_component_owns_the_files_its_decorator_points_at(self):
        write(
            self.repo,
            {
                "src/app/feed/feed.component.ts": """
                    import { Component } from '@angular/core';
                    @Component({
                      selector: 'app-feed',
                      templateUrl: '../templates/feed.html',
                      styleUrl: './feed.theme.scss',
                    })
                    export class FeedComponent {}
                """,
                "src/app/templates/feed.html": "<ul></ul>",
                "src/app/feed/feed.theme.scss": "ul { margin: 0; }",
            },
        )
        inventory, _ = self.scan()
        unit = inventory["components"][0]

        self.assertEqual(unit["template"], "src/app/templates/feed.html")
        self.assertEqual(unit["styles"], ["src/app/feed/feed.theme.scss"])
        self.assertEqual(unit["selector"], "app-feed")

    def test_workspace_picks_the_application_and_disambiguates_labels(self):
        write(
            self.repo,
            {
                "angular.json": json.dumps(
                    {
                        "projects": {
                            "shared": {"projectType": "library", "sourceRoot": "libs/shared/src"},
                            "web": {"projectType": "application", "sourceRoot": "apps/web/src"},
                        },
                        "defaultProject": "web",
                    }
                ),
                "libs/shared/src/lib/button.ts": COMPONENT.format(
                    stem="button", cls="ButtonComponent", selector="lib-button"
                ),
            },
        )
        component(self.repo, "apps/web/src/app/list", "list", "ListComponent", "app-list")
        component(self.repo, "apps/web/src/app/admin/list", "list", "ListComponent", "admin-list")
        inventory, _ = self.scan()

        self.assertEqual(inventory["source_root"], "apps/web/src/app")
        self.assertEqual(
            sorted(c["label"] for c in inventory["components"]), ["admin-list", "app-list"]
        )


class StoreTest(unittest.TestCase):
    """A store is the one contract every component shares, so it gates the fan-out."""

    def setUp(self):
        self.repo = init_repo()
        component(self.repo, "src/app/feed", "feed.component", "FeedComponent", "app-feed")

    def test_no_store_means_no_store_rules(self):
        namespace, prompts = run_workflow(self.repo)
        inventory = namespace["INVENTORY"]

        self.assertEqual(inventory["state_libraries"], [])
        self.assertEqual(inventory["store"], [])
        for prompt in prompts.values():
            self.assertNotIn("Redux Toolkit", prompt)

    def test_ngrx_is_detected_and_its_rules_reach_foundation_and_components(self):
        write(
            self.repo,
            {
                "src/app/state/feed.reducer.ts": """
                    import { createReducer, on } from '@ngrx/store';
                    export const feedReducer = createReducer({ stories: [] });
                """,
                "src/app/state/feed.effects.ts": """
                    import { Injectable } from '@angular/core';
                    import { Actions, createEffect } from '@ngrx/effects';
                    @Injectable()
                    export class FeedEffects {}
                """,
            },
        )
        namespace, prompts = run_workflow(self.repo)
        inventory = namespace["INVENTORY"]

        self.assertEqual(inventory["state_libraries"], ["ngrx"])
        self.assertEqual(
            inventory["store"],
            ["src/app/state/feed.effects.ts", "src/app/state/feed.reducer.ts"],
        )
        # The effects class is @Injectable, so it stays a service too — stage 1 owns both.
        self.assertIn("src/app/state/feed.effects.ts", inventory["services"])
        for label in ("foundation", "feed"):
            self.assertIn("Redux Toolkit", prompts[label])
            self.assertIn("useAppSelector", prompts[label])
        self.assertIn("store_api", prompts["foundation"])
        self.assertIn("@reduxjs/toolkit", prompts["scaffold"])
        self.assertIn("Provider store=", prompts["combine"])

    def test_ngxs_is_detected_too(self):
        write(
            self.repo,
            {
                "src/app/state/feed.state.ts": """
                    import { State } from '@ngxs/store';
                    @State({ name: 'feed', defaults: { stories: [] } })
                    export class FeedState {}
                """,
            },
        )
        namespace, prompts = run_workflow(self.repo)

        self.assertEqual(namespace["INVENTORY"]["state_libraries"], ["ngxs"])
        self.assertIn("ngxs", prompts["foundation"])


if __name__ == "__main__":
    unittest.main()
