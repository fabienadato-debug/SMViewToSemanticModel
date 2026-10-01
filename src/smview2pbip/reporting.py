"""Generate conversion diagnostics and preserved business metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from smview2pbip.ir import ModelPlan
from smview2pbip.schema import SemanticView


def _collect_unknown_fields(value: Any, path: str = "$.") -> list[str]:
    unknown: list[str] = []
    if isinstance(value, BaseModel):
        for field_name in sorted((value.model_extra or {}).keys()):
            unknown.append(f"{path}{field_name}")
        for field_name in type(value).model_fields:
            child = getattr(value, field_name)
            unknown.extend(_collect_unknown_fields(child, f"{path}{field_name}."))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            unknown.extend(_collect_unknown_fields(child, f"{path}[{index}]."))
    elif isinstance(value, dict):
        for key, child in value.items():
            unknown.extend(_collect_unknown_fields(child, f"{path}{key}."))
    return unknown


def write_conversion_reports(plan: ModelPlan, source: SemanticView, output: Path) -> None:
    """Write JSON/Markdown diagnostics and non-executable source metadata."""

    warning_count = sum(item.severity == "warning" for item in plan.diagnostics)
    report = {
        "sourceSemanticView": source.name,
        "targetModel": plan.name,
        "summary": {
            "tables": len(plan.tables),
            "columns": sum(len(table.columns) for table in plan.tables),
            "measures": sum(len(table.measures) for table in plan.tables),
            "relationships": len(plan.relationships),
            "warnings": warning_count,
        },
        "unknownFields": _collect_unknown_fields(source),
        "diagnostics": [
            {
                "severity": item.severity,
                "code": item.code,
                "object": item.object_name,
                "message": item.message,
            }
            for item in plan.diagnostics
        ],
    }
    (output / "conversion-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    markdown = [
        f"# Conversion report: {plan.name}",
        "",
        f"- Tables: {report['summary']['tables']}",
        f"- Columns: {report['summary']['columns']}",
        f"- Measures: {report['summary']['measures']}",
        f"- Relationships: {report['summary']['relationships']}",
        f"- Warnings: {warning_count}",
        "",
        "## Diagnostics",
        "",
    ]
    if plan.diagnostics:
        for item in plan.diagnostics:
            target = f" ({item.object_name})" if item.object_name else ""
            markdown.append(f"- **{item.severity.upper()} `{item.code}`{target}:** {item.message}")
    else:
        markdown.append("No diagnostics.")
    if report["unknownFields"]:
        markdown.extend(["", "## Unknown YAML fields", ""])
        markdown.extend(f"- `{path}`" for path in report["unknownFields"])
    (output / "conversion-report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")

    business_rules = [
        f"# Source business metadata: {source.name}",
        "",
        "These instructions and verified queries are preserved for review. They are not executed by Power BI.",
        "",
    ]
    for instruction_name, instruction in source.module_custom_instructions.items():
        business_rules.extend([f"## {instruction_name}", "", instruction, ""])
    business_rules.extend(["## Verified queries", ""])
    for query in source.verified_queries:
        business_rules.extend(
            [
                f"### {query.name}",
                "",
                f"**Question:** {query.question}",
                "",
                "```sql",
                query.sql,
                "```",
                "",
            ]
        )
    (output / "source-business-metadata.md").write_text(
        "\n".join(business_rules), encoding="utf-8"
    )
