"""Command-line interface for smview2pbip."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from smview2pbip.generators.pbip import write_pbip
from smview2pbip.planner import build_model_plan
from smview2pbip.reporting import write_conversion_reports
from smview2pbip.schema import load_semantic_view

app = typer.Typer(no_args_is_help=True, help="Convert Snowflake Semantic Views to PBIP/TMDL.")


@app.command()
def validate(
    input_path: Annotated[
        Path,
        typer.Option("--input", "-i", exists=True, dir_okay=False, readable=True),
    ],
) -> None:
    """Validate a Snowflake Semantic View YAML definition."""

    try:
        semantic_view = load_semantic_view(input_path)
    except (OSError, ValueError, ValidationError) as error:
        typer.echo(f"Validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Valid semantic view '{semantic_view.name}': "
        f"{len(semantic_view.tables)} tables, "
        f"{len(semantic_view.relationships)} relationships."
    )


@app.command()
def convert(
    input_path: Annotated[
        Path,
        typer.Option("--input", "-i", exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path, typer.Option("--output", "-o")],
    model_name: Annotated[str | None, typer.Option("--model-name")] = None,
    default_culture: Annotated[str, typer.Option("--default-culture")] = "en-US",
    snowflake_server: Annotated[str, typer.Option("--snowflake-server")] = "SERVER",
    snowflake_warehouse: Annotated[str, typer.Option("--snowflake-warehouse")] = "WAREHOUSE",
    snowflake_role: Annotated[str, typer.Option("--snowflake-role")] = "ROLE",
    strict: Annotated[bool, typer.Option("--strict")] = False,
) -> None:
    """Convert a Semantic View YAML file to a Power BI PBIP/TMDL project."""

    try:
        semantic_view = load_semantic_view(input_path)
        plan = build_model_plan(semantic_view, model_name, default_culture)
    except (OSError, ValueError, ValidationError) as error:
        typer.echo(f"Conversion failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    warnings = [item for item in plan.diagnostics if item.severity == "warning"]
    if strict and warnings:
        typer.echo(f"Conversion stopped: {len(warnings)} warning(s) in strict mode.", err=True)
        raise typer.Exit(code=2)

    output.mkdir(parents=True, exist_ok=True)
    pbip_path = write_pbip(
        plan,
        output,
        snowflake_server,
        snowflake_warehouse,
        snowflake_role,
    )
    write_conversion_reports(plan, semantic_view, output)
    typer.echo(
        f"Generated {pbip_path} with {len(plan.tables)} tables, "
        f"{len(plan.relationships)} relationships, and {len(warnings)} warning(s)."
    )


if __name__ == "__main__":
    app()
