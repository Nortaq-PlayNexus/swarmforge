"""Rich CLI display for SwarmForge."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


console = Console()


class Display:
    def print_workflow_start(self, name: str, steps: int):
        console.print()
        console.print(
            Panel(
                f"[bold cyan]SwarmForge[/bold cyan]\n\n"
                f"Workflow: [bold]{name}[/bold]\n"
                f"Steps: {steps}",
                border_style="blue", expand=True,
            )
        )
        console.print()

    def print_step_start(self, step: str, agent: str):
        console.print(f"  [bold blue]→[/bold blue] [{step}] Running agent [cyan]{agent}[/cyan]...")

    def print_step_complete(self, step: str, success: bool):
        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {icon} [{step}] Complete")

    def print_step_skip(self, step: str, condition: str):
        console.print(f"  [dim]⊘ [{step}] Skipped (condition: {condition})[/dim]")

    def print_step_error(self, step: str, error: str):
        console.print(f"  [bold red]✗[/bold red] [{step}] {error}")

    def print_workflow_complete(self, result: dict):
        console.print()
        table = Table(box=box.ROUNDED, title="Workflow Results")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="cyan")
        table.add_row("Status", "[green]SUCCESS[/green]" if result.get("success") else "[red]FAILED[/red]")
        table.add_row("Steps Completed", str(result.get("steps_completed", 0)))
        table.add_row("Elapsed", f"{result.get('elapsed_seconds', 0)}s")
        console.print(table)
        console.print()

    def print_workflow_diagram(self, mermaid_code: str):
        console.print()
        console.print(
            Panel(
                f"[bold cyan]Workflow Diagram[/bold cyan]\n\n"
                f"```mermaid\n{mermaid_code}\n```",
                border_style="blue", expand=True,
            )
        )
        console.print()

    def print_templates_list(self, templates: dict[str, dict]):
        console.print()
        table = Table(box=box.ROUNDED, title="Available Workflow Templates")
        table.add_column("Name", style="bold cyan")
        table.add_column("Description", style="white")
        table.add_column("Steps", justify="right", style="green")
        table.add_column("Agents", justify="right", style="yellow")
        for name, tmpl in templates.items():
            table.add_row(
                name,
                tmpl.get("description", ""),
                str(len(tmpl.get("steps", []))),
                str(len(tmpl.get("agents", []))),
            )
        console.print(table)
        console.print()

    def print_step_timeline(self, history: list[dict]):
        console.print()
        table = Table(box=box.ROUNDED, title="Execution Timeline")
        table.add_column("Step", style="bold cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right", style="yellow")
        table.add_column("Retries", justify="right", style="magenta")
        table.add_column("Error", style="red")
        for entry in history:
            status = "[green]OK[/green]" if entry.get("success") else "[red]FAIL[/red]"
            if entry.get("skipped"):
                status = "[dim]SKIP[/dim]"
            table.add_row(
                entry.get("name", ""),
                status,
                f"{entry.get('elapsed_seconds', 0):.2f}s",
                str(entry.get("retries_used", 0)),
                entry.get("error", "")[:60],
            )
        console.print(table)
        console.print()

    def print_error(self, message: str):
        console.print(f"  [bold red]✗[/bold red] {message}")

    def print_success(self, message: str):
        console.print(f"  [bold green]✓[/bold green] {message}")

    def print_info(self):
        console.print()
        console.print(
            Panel(
                "[bold cyan]SwarmForge[/bold cyan] — Multi-Agent AI Orchestrator\n\n"
                "Design, deploy, and monitor collaborative agent workflows.\n\n"
                "[bold]Commands:[/bold]\n"
                "  swarmforge run <workflow.yaml>      Execute a workflow\n"
                "  swarmforge validate <workflow.yaml> Validate workflow syntax\n"
                "  swarmforge info                     Show this info\n\n"
                "[bold]Workflow YAML:[/bold]\n"
                "  name: my-workflow\n"
                "  agents:\n"
                "    - name: researcher\n"
                "      type: llm\n"
                "      model: gpt-4o\n"
                "      system_prompt: \"You are a research agent.\"\n"
                "  steps:\n"
                "    - name: research\n"
                "      agent: researcher\n"
                "      input:\n"
                "        topic: \"AI safety\"\n\n"
                "[bold]Agent Types:[/bold]  llm | tool | router | aggregate",
                border_style="blue", expand=True,
            )
        )
        console.print()
