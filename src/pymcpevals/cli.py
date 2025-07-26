"""CLI interface for pymcpevals."""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import load_yaml_config, save_config_template
from .types import EvaluationCase, EvaluationConfig, EvaluationResult, EvaluationSummary

console = Console()


@click.group()
def cli() -> None:
    """PyMCPEvals - Evaluate MCP server implementations."""


@cli.command()
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.option("--server", help="Override server command (e.g., 'python server.py')")
@click.option("--server-url", help="Override server URL for HTTP transport")
@click.option("--model", help="Override LLM model (e.g., 'gpt-4', 'claude-3-opus-20240229')")
@click.option("--provider", help="Override LLM provider (e.g., 'openai', 'anthropic')")
@click.option("--parallel", is_flag=True, help="Run evaluations in parallel")
@click.option(
    "--output",
    type=click.Choice(["table", "detailed", "json", "junit"]),
    default="detailed",
    help="Output format (detailed shows enhanced reporting)",
)
@click.option("--output-file", type=click.Path(path_type=Path), help="Save output to file")
@click.option("--threshold", type=float, help="Override minimum score threshold")
def run(
    config_path: Path,
    server: str | None,
    server_url: str | None,
    model: str | None,
    provider: str | None,
    parallel: bool,
    output: str,
    output_file: Path | None,
    threshold: float | None,
) -> None:
    """Run evaluations from a YAML configuration file."""
    try:
        # Load configuration
        config = load_yaml_config(config_path)

        # Apply command line overrides
        if server:
            config.server.command = server.split()
            config.server.url = None
        elif server_url:
            config.server.url = server_url
            config.server.command = None

        if model:
            config.model.name = model
        if provider:
            config.model.provider = provider
        if parallel:
            config.parallel = parallel

        # Run evaluations
        asyncio.run(_run_evaluations(config, threshold, output, output_file, config_path))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command("eval")
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.argument("server_path", type=click.Path(exists=True, path_type=Path))
@click.option("--model", default="gpt-4", help="LLM model to use")
def eval_simple(config_path: Path, server_path: Path, model: str) -> None:
    """Simple evaluation interface: pymcpevals evals.yaml server.py"""
    try:
        # Load configuration
        config = load_yaml_config(config_path)

        # Override server to use the provided script
        config.server.command = ["python", str(server_path)]
        config.server.url = None
        config.model.name = model

        # Run evaluations
        asyncio.run(_run_evaluations(config, config_path=config_path))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command("init")
@click.argument("output_path", type=click.Path(path_type=Path), default="evals.yaml")
def init_config(output_path: Path) -> None:
    """Create a template configuration file."""
    try:
        save_config_template(output_path)
        console.print(f"[green]✓[/green] Configuration template created: {output_path}")
        console.print("\nEdit the file and run: [bold]pymcpevals run evals.yaml[/bold]")
    except Exception as e:
        console.print(f"[red]Error creating template: {e}[/red]")
        sys.exit(1)


async def _run_evaluations(
    config: EvaluationConfig,
    threshold_override: float | None = None,
    output_format: str = "table",
    output_file: Path | None = None,
    config_path: Path | None = None,
) -> None:
    """Run all evaluations and display results."""
    results: list[EvaluationResult | None] = []

    console.print(f"[bold blue]Running {len(config.evaluations)} evaluations...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        if config.parallel:
            # Run evaluations in parallel
            tasks = []
            for eval_case in config.evaluations:
                task = progress.add_task(f"Evaluating: {eval_case.name}")
                tasks.append(
                    _run_single_evaluation(config, eval_case, threshold_override, config_path)
                )

            gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(gathered_results):
                if isinstance(result, Exception):
                    console.print(f"[red]Error in {config.evaluations[i].name}: {result}[/red]")
                    results.append(None)
                elif isinstance(result, EvaluationResult):
                    results.append(result)
                    progress.update(progress.task_ids[i], completed=True)
                else:
                    # Should not happen, but handle gracefully
                    results.append(None)
        else:
            # Run evaluations sequentially
            for eval_case in config.evaluations:
                task = progress.add_task(f"Evaluating: {eval_case.name}")

                try:
                    result = await _run_single_evaluation(
                        config, eval_case, threshold_override, config_path
                    )
                    results.append(result)
                    progress.update(task, completed=True)
                except Exception as e:
                    console.print(f"[red]Error in {eval_case.name}: {e}[/red]")
                    results.append(None)

    # Filter out None results
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        console.print("[red]No successful evaluations![/red]")
        sys.exit(1)

    # Create summary
    total = len(config.evaluations)
    passed = sum(1 for r in valid_results if r.passed)
    failed = total - passed
    avg_score = sum(r.average_score for r in valid_results) / len(valid_results)

    summary = EvaluationSummary(
        total_evaluations=total,
        passed=passed,
        failed=failed,
        average_score=avg_score,
        results=valid_results,
    )

    # Output results
    if output_format == "table":
        _output_table(summary)
    elif output_format == "detailed":
        _output_detailed(summary)
    elif output_format == "json":
        _output_json(summary, output_file)
    elif output_format == "junit":
        _output_junit(summary, output_file)

    # Exit with error code if any evaluations failed
    if failed > 0:
        sys.exit(1)


async def _run_single_evaluation(
    config: EvaluationConfig,
    eval_case: EvaluationCase,
    threshold_override: float | None = None,
    config_path: Path | None = None,
) -> EvaluationResult:
    """Run a single evaluation."""
    from .core import evaluate_case

    server_source = config.server.get_server_source(str(config_path) if config_path else None)

    result = await evaluate_case(
        server_source=server_source,
        case=eval_case,
        model=config.model.model_string,
    )

    # Apply threshold logic: CLI override takes precedence, then case threshold, then default
    threshold = threshold_override or eval_case.threshold or 3.0
    # Update the passed status based on the appropriate threshold
    result.passed = result.average_score >= threshold

    return result


def _output_table(summary: EvaluationSummary) -> None:
    """Output results as a rich table."""
    console.print()

    # Results table
    table = Table(title="Evaluation Results")
    table.add_column("Name", style="cyan")
    table.add_column("Accuracy", justify="center")
    table.add_column("Completeness", justify="center")
    table.add_column("Relevance", justify="center")
    table.add_column("Clarity", justify="center")
    table.add_column("Reasoning", justify="center")
    table.add_column("Average", justify="center")
    table.add_column("Status", justify="center")

    for result in summary.results:
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"

        # Handle cases where prompt might be None (trajectory mode)
        prompt_display = result.prompt or "Trajectory evaluation"
        table.add_row(
            prompt_display[:30] + "..." if len(prompt_display) > 30 else prompt_display,
            f"{result.accuracy:.1f}",
            f"{result.completeness:.1f}",
            f"{result.relevance:.1f}",
            f"{result.clarity:.1f}",
            f"{result.reasoning:.1f}",
            f"{result.average_score:.2f}",
            status,
        )

    console.print(table)
    console.print()
    console.print(f"[bold]Summary:[/bold] {summary}")


def _output_detailed(summary: EvaluationSummary) -> None:
    """Output enhanced table with server developer insights."""
    console.print()
    console.print("[bold blue]MCP Server Evaluation Results[/bold blue]")
    console.print()

    # Main results table
    table = Table(title="Evaluation Results")
    table.add_column("Test", style="cyan", width=25)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Score", justify="center", width=6)
    table.add_column("Tools Used", style="yellow", width=20)
    table.add_column("Time", justify="center", width=8)
    table.add_column("Errors", justify="center", width=8)
    table.add_column("Notes", width=30)

    for result in summary.results:
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"

        # Test name (prompt or trajectory)
        test_name = result.prompt or "Multi-turn test"
        if len(test_name) > 25:
            test_name = test_name[:22] + "..."

        # Tools used
        tools_display = ""
        if result.tools_used:
            tools_display = ", ".join(result.tools_used)
            if len(tools_display) > 20:
                tools_display = tools_display[:17] + "..."
        else:
            tools_display = "[dim]None[/dim]"

        # Execution time with color coding
        time_ms = result.total_execution_time_ms
        if time_ms > 3000:
            time_display = f"[red]{time_ms:.0f}ms[/red]"
        elif time_ms > 1000:
            time_display = f"[yellow]{time_ms:.0f}ms[/yellow]"
        else:
            time_display = f"{time_ms:.0f}ms"

        # Error count
        error_count = result.failed_tool_calls
        error_display = f"[red]{error_count}[/red]" if error_count > 0 else "0"

        # Notes (errors or key insights)
        notes = ""
        if result.error:
            notes = result.error[:30] + "..." if len(result.error) > 30 else result.error
        elif not result.passed:
            # Show brief comment for failed tests
            notes = (
                result.overall_comments[:30] + "..."
                if len(result.overall_comments) > 30
                else result.overall_comments
            )
        else:
            notes = "[dim]OK[/dim]"

        table.add_row(
            test_name,
            status,
            f"{result.average_score:.1f}",
            tools_display,
            time_display,
            error_display,
            notes,
        )

    console.print(table)
    console.print()

    # Tool call details for failed evaluations
    failed_results = [r for r in summary.results if not r.passed]
    if failed_results:
        console.print("[bold red]🔧 Failed Test Details:[/bold red]")
        for result in failed_results:
            test_name = result.prompt or "Multi-turn test"
            console.print(f"[bold]• {test_name[:50]}{'...' if len(test_name) > 50 else ''}[/bold]")

            # Show tool call details for debugging
            if result.tool_call_details:
                console.print("  Tool calls:")
                for call in result.tool_call_details:
                    status_icon = "✅" if call.get("success", True) else "❌"
                    tool_name = call.get("tool_name", "unknown")
                    time_ms = call.get("execution_time_ms", 0)

                    if call.get("success", True):
                        console.print(f"    {status_icon} {tool_name} ({time_ms:.0f}ms)")
                    else:
                        error_msg = call.get("error_message", "Unknown error")
                        console.print(
                            f"    {status_icon} {tool_name} ({time_ms:.0f}ms) - [red]{error_msg}[/red]"
                        )

            # Show key failure info
            if result.error:
                console.print(f"  [red]Error: {result.error}[/red]")
            elif result.overall_comments:
                console.print(f"  Issue: {result.overall_comments}")

            console.print()

    # Summary
    console.print(f"[bold]Summary:[/bold] {summary}")


def _output_json(summary: EvaluationSummary, output_file: Path | None) -> None:
    """Output results as JSON."""
    import json

    json_data = summary.model_dump(mode="json")
    json_str = json.dumps(json_data, indent=2)

    if output_file:
        output_file.write_text(json_str)
        console.print(f"Results saved to: {output_file}")
    else:
        console.print(json_str)


def _output_junit(summary: EvaluationSummary, output_file: Path | None) -> None:
    """Output results as JUnit XML."""
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append(
        f'<testsuites tests="{summary.total_evaluations}" failures="{summary.failed}">',
    )
    xml_lines.append('  <testsuite name="MCP Evaluations">')

    for result in summary.results:
        prompt_display = result.prompt or "Trajectory evaluation"
        name = prompt_display[:50].replace('"', "&quot;")
        xml_lines.append(f'    <testcase name="{name}">')

        if not result.passed:
            msg = f"Average score {result.average_score:.2f} below threshold"
            xml_lines.append(f'      <failure message="{msg}">')
            xml_lines.append(f"        {result.overall_comments}")
            xml_lines.append("      </failure>")

        xml_lines.append("    </testcase>")

    xml_lines.append("  </testsuite>")
    xml_lines.append("</testsuites>")

    xml_content = "\n".join(xml_lines)

    if output_file:
        output_file.write_text(xml_content)
        console.print(f"JUnit XML saved to: {output_file}")
    else:
        console.print(xml_content)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
