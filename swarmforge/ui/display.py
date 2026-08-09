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
