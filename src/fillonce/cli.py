from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fillonce import __version__
from fillonce.demo import create_demo
from fillonce.models import FillPlan
from fillonce.pipeline import apply_plan, build_plan, extract_facts, inspect_form

app = typer.Typer(
    name="fillonce",
    help="Fill native PDF forms from existing facts, with evidence for every answer.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version(value: bool) -> None:
    if value:
        console.print(f"FillOnce {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version, is_eager=True, help="Show the version and exit."),
    ] = None,
) -> None:
    """Never invent a fact. Never submit without you."""


def _write_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _plan_table(plan: FillPlan) -> Table:
    table = Table(title="Fill plan", header_style="bold green", show_lines=False)
    table.add_column("Field", style="bold")
    table.add_column("Proposed value")
    table.add_column("Status")
    table.add_column("Confidence", justify="right")
    table.add_column("Evidence", overflow="fold")
    colors = {"ready": "green", "review": "yellow", "conflict": "red", "missing": "dim"}
    for item in plan.fields:
        evidence = "-"
        if item.evidence:
            evidence = f"{Path(item.evidence.source).name} | {item.evidence.locator}"
        table.add_row(
            item.field.label,
            item.value or "-",
            f"[{colors.get(item.status, 'white')}]{item.status}[/]",
            f"{item.confidence:.0%}",
            evidence,
        )
    return table


@app.command("inspect")
def inspect_command(
    form: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Blank PDF form")],
    output: Annotated[Path, typer.Option("--output", "-o", help="JSON output path")] = Path(
        "fields.json"
    ),
) -> None:
    """List native fields in a PDF without reading source documents."""
    fields = inspect_form(form)
    _write_json([asdict(field) for field in fields], output)
    console.print(f"[green]OK[/] Found {len(fields)} fields -> [bold]{output}[/]")


@app.command("extract")
def extract_command(
    sources: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o", help="JSON output path")] = Path(
        "facts.json"
    ),
) -> None:
    """Extract reusable facts and their exact source locations."""
    facts = extract_facts(sources)
    _write_json([asdict(fact) for fact in facts], output)
    console.print(f"[green]OK[/] Extracted {len(facts)} facts -> [bold]{output}[/]")


@app.command("plan")
def plan_command(
    form: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Blank PDF form")],
    sources: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("fill-plan.json"),
    agent_model: Annotated[str | None, typer.Option(help="Opt-in OpenAI-compatible model")] = None,
    agent_base_url: Annotated[str | None, typer.Option(help="OpenAI-compatible API base URL")] = None,
    agent_api_key: Annotated[
        str | None, typer.Option(envvar="FILLONCE_AGENT_API_KEY", help="Agent API key")
    ] = None,
) -> None:
    """Propose answers without modifying the PDF."""
    fill_plan = build_plan(
        form,
        sources,
        agent_model=agent_model,
        agent_base_url=agent_base_url,
        agent_api_key=agent_api_key,
    )
    _write_json(fill_plan.to_dict(), output)
    console.print(_plan_table(fill_plan))
    summary = fill_plan.summary()
    console.print(
        f"[green]OK[/] Plan saved to [bold]{output}[/] | "
        f"{summary['ready']} ready, {summary['review']} review, "
        f"{summary['conflict']} conflict, {summary['missing']} missing"
    )


@app.command("apply")
def apply_command(
    plan_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("completed.pdf"),
    form: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Override original form path in the plan"),
    ] = None,
    flatten: Annotated[
        bool,
        typer.Option(help="Create a static PDF with form widgets removed"),
    ] = False,
) -> None:
    """Apply selected plan items and create portable JSON + HTML audits."""
    fill_plan = FillPlan.from_json_file(plan_file)
    apply_plan(fill_plan, output, form_path=form, flatten=flatten)
    mode = "Flattened" if flatten else "Editable"
    console.print(f"[green]OK[/] {mode} PDF -> [bold]{output}[/]")
    audit_stem = output.with_suffix("").name
    console.print(f"  Evidence -> {audit_stem}.audit.json / {audit_stem}.audit.html")


@app.command("fill")
def fill_command(
    form: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Blank PDF form")],
    sources: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("completed.pdf"),
    flatten: Annotated[
        bool,
        typer.Option(help="Create a static PDF with form widgets removed"),
    ] = False,
) -> None:
    """Plan and apply only exact, conflict-free matches."""
    fill_plan = build_plan(form, sources)
    plan_path = output.with_name(f"{output.stem}.plan.json")
    _write_json(fill_plan.to_dict(), plan_path)
    apply_plan(fill_plan, output, flatten=flatten)
    console.print(_plan_table(fill_plan))
    mode = "flattened" if flatten else "editable"
    console.print(f"[green]OK[/] Safe matches filled ({mode}) -> [bold]{output}[/]")
    console.print(f"  Review plan -> {plan_path}")


@app.command("demo")
def demo_command(
    output_dir: Annotated[Path, typer.Argument(help="Directory to create")] = Path("fillonce-demo"),
) -> None:
    """Generate and fill a synthetic application - no personal files needed."""
    paths = create_demo(output_dir)
    console.print("[green]OK[/] Demo created. Open these files:")
    for label, path in paths.items():
        console.print(f"  [bold]{label:12}[/] {path}")


@app.command("serve")
def serve_command(
    host: Annotated[str, typer.Option(help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8765,
) -> None:
    """Start the private, stateless review UI."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter("Install the web extra first: uv sync --extra web") from exc
    if host not in {"127.0.0.1", "localhost", "::1"}:
        console.print(
            "[yellow]Warning:[/] non-loopback binding exposes the UI and uploaded documents to your network."
        )
    console.print(f"[green]FillOnce[/] review UI -> http://{host}:{port}")
    os.environ.setdefault("FILLONCE_WEB", "1")
    uvicorn.run("fillonce.web:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    app()
