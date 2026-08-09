"""SwarmForge — CLI entry point."""

import argparse
import sys
import yaml
from pathlib import Path

from swarmforge import __version__
from swarmforge.core.engine import SwarmEngine
from swarmforge.core.workflow import Workflow
from swarmforge.core.templates import ALL_TEMPLATES
from swarmforge.core.visualizer import WorkflowVisualizer
from swarmforge.ui.display import Display


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swarmforge",
        description="Multi-agent AI orchestrator — design, deploy, and monitor agent workflows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Execute a workflow")
    run.add_argument("workflow", type=str, help="Path to workflow YAML file")
    run.add_argument("--var", action="append", default=[], help="Override variable: --var key=value")

    validate = sub.add_parser("validate", help="Validate a workflow file")
    validate.add_argument("workflow", type=str, help="Path to workflow YAML file")

    info = sub.add_parser("info", help="Show SwarmForge info and built-in agents")

    sub.add_parser("templates", help="List available workflow templates")

    new_cmd = sub.add_parser("new", help="Scaffold a workflow from a template")
    new_cmd.add_argument("--template", type=str, required=True,
                         help="Template name (research, data-pipeline, code-review, customer-support)")
    new_cmd.add_argument("--output", type=str, default="workflow.yaml",
                         help="Output file path (default: workflow.yaml)")

    visualize = sub.add_parser("visualize", help="Generate Mermaid diagram from workflow YAML")
    visualize.add_argument("workflow", type=str, help="Path to workflow YAML file")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    display = Display()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "info":
        display.print_info()
        return 0

    if args.command == "templates":
        display.print_templates_list(ALL_TEMPLATES)
        return 0

    if args.command == "new":
        template_name = args.template
        if template_name not in ALL_TEMPLATES:
            display.print_error(f"Unknown template '{template_name}'. Available: {', '.join(ALL_TEMPLATES.keys())}")
            return 1

        import copy
        template_data = copy.deepcopy(ALL_TEMPLATES[template_name])
        output_path = Path(args.output)

        with open(output_path, "w") as f:
            yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

        display.print_success(f"Created workflow '{template_name}' at {output_path}")
        return 0

    if args.command == "visualize":
        path = Path(args.workflow)
        if not path.exists():
            display.print_error(f"File not found: {path}")
            return 1

        with open(path) as f:
            spec = yaml.safe_load(f)

        try:
            wf = Workflow.from_dict(spec)
        except Exception as e:
            display.print_error(f"Invalid workflow: {e}")
            return 1

        viz = WorkflowVisualizer(wf)
        mermaid_code = viz.generate()
        display.print_workflow_diagram(mermaid_code)
        return 0

    if args.command == "validate":
        path = Path(args.workflow)
        if not path.exists():
            display.print_error(f"File not found: {path}")
            return 1
        with open(path) as f:
            spec = yaml.safe_load(f)
        try:
            wf = Workflow.from_dict(spec)
            display.print_success(f"Workflow '{wf.name}' is valid ({len(wf.agents)} agents, {len(wf.steps)} steps)")
            return 0
        except Exception as e:
            display.print_error(f"Invalid workflow: {e}")
            return 1

    if args.command == "run":
        path = Path(args.workflow)
        if not path.exists():
            display.print_error(f"File not found: {path}")
            return 1

        overrides = {}
        for item in args.var:
            if "=" in item:
                k, v = item.split("=", 1)
                overrides[k] = v

        with open(path) as f:
            spec = yaml.safe_load(f)

        if overrides:
            spec.setdefault("variables", {}).update(overrides)

        try:
            wf = Workflow.from_dict(spec)
        except Exception as e:
            display.print_error(f"Invalid workflow: {e}")
            return 1

        engine = SwarmEngine(wf, display=display)
        result = engine.run()

        if result.get("execution_history"):
            display.print_step_timeline(result["execution_history"])

        if result.get("success"):
            display.print_success("Workflow completed successfully!")
            return 0
        else:
            display.print_error(f"Workflow failed: {result.get('error', 'unknown')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
