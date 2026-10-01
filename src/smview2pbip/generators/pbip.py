"""Write a complete local PBIP project from a model plan."""

from __future__ import annotations

import json
import re
from pathlib import Path

from smview2pbip.generators.tmdl import (
    render_expressions,
    render_model,
    render_relationships,
    render_table,
)
from smview2pbip.ir import ModelPlan


def _safe_file_name(name: str) -> str:
    return re.sub(r"[<>:\"/\\|?*]", "_", name)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_pbip(
    plan: ModelPlan,
    output: Path,
    server: str,
    warehouse: str,
    role: str,
) -> Path:
    """Write PBIP, PBIR, PBISM, and TMDL files and return the PBIP path."""

    project_name = _safe_file_name(plan.name)
    semantic_model = output / f"{project_name}.SemanticModel"
    definition = semantic_model / "definition"
    tables_path = definition / "tables"
    report = output / f"{project_name}.Report"
    report_definition = report / "definition"
    tables_path.mkdir(parents=True, exist_ok=True)
    report_definition.mkdir(parents=True, exist_ok=True)

    _write_json(
        semantic_model / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {"qnaEnabled": True},
        },
    )
    _write_json(
        report / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{project_name}.SemanticModel"}},
        },
    )
    _write_json(
        output / f"{project_name}.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{project_name}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    (definition / "database.tmdl").write_text(
        "database Model\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n",
        encoding="utf-8",
    )
    (definition / "model.tmdl").write_text(render_model(plan), encoding="utf-8")
    (definition / "relationships.tmdl").write_text(render_relationships(plan), encoding="utf-8")
    (definition / "expressions.tmdl").write_text(
        render_expressions(server, warehouse, role), encoding="utf-8"
    )
    for table in plan.tables:
        (tables_path / f"{_safe_file_name(table.name)}.tmdl").write_text(
            render_table(table), encoding="utf-8"
        )
    return output / f"{project_name}.pbip"
