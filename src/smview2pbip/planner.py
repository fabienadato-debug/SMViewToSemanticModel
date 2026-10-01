"""Build a Power BI conversion plan from a validated Semantic View."""

from __future__ import annotations

import re

from smview2pbip.generators.dax import (
    UnsupportedExpressionError,
    referenced_columns,
    translate_metric,
)
from smview2pbip.ir import (
    ColumnPlan,
    Diagnostic,
    MeasurePlan,
    ModelPlan,
    RelationshipPlan,
    TablePlan,
)
from smview2pbip.schema import SemanticView


def map_data_type(data_type: str | None) -> str:
    """Map a Snowflake type declaration to a TMDL data type."""

    if data_type is None:
        return "string"
    normalized = data_type.strip().upper()
    if normalized.startswith(("VARCHAR", "CHAR", "TEXT")):
        return "string"
    if normalized.startswith(("DATE", "TIMESTAMP", "DATETIME")):
        return "dateTime"
    if normalized.startswith("BOOLEAN"):
        return "boolean"
    number_match = re.match(r"(?:NUMBER|DECIMAL|NUMERIC)\((\d+),(\d+)\)", normalized)
    if number_match:
        scale = int(number_match.group(2))
        return "int64" if scale == 0 else "decimal"
    if normalized.startswith(("NUMBER", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE")):
        return "decimal"
    raise ValueError(f"Unsupported Snowflake data type: {data_type}")


def _measure_format(name: str, expression: str) -> str:
    upper_name = name.upper()
    if "RATE" in upper_name or "TAUX" in upper_name or "100*" in expression.replace(" ", ""):
        return "#,##0.0"
    if "QTY" in upper_name or "QUANTITY" in upper_name:
        return "#,##0"
    return "#,##0.00"


def build_model_plan(
    semantic_view: SemanticView,
    model_name: str | None = None,
    culture: str = "en-US",
) -> ModelPlan:
    """Create a deterministic model plan and collect non-fatal diagnostics."""

    plan = ModelPlan(name=model_name or semantic_view.name, culture=culture)
    tables_by_name: dict[str, TablePlan] = {}
    source_mappings: dict[str, dict[str, str]] = {}

    for source_table in semantic_view.tables:
        table = TablePlan(
            name=source_table.name,
            database=source_table.base_table.database,
            schema=source_table.base_table.schema_name,
            source_table=source_table.base_table.table,
            description=source_table.description,
        )
        mapping: dict[str, str] = {}
        for dimension in source_table.dimensions:
            table.columns.append(
                ColumnPlan(
                    name=dimension.name,
                    source_column=dimension.expr,
                    data_type=map_data_type(dimension.data_type),
                    description=dimension.description,
                    synonyms=tuple(dimension.synonyms),
                )
            )
            mapping[dimension.expr.upper()] = dimension.name
        for fact in source_table.facts:
            technical_name = f"__{fact.name}"
            table.columns.append(
                ColumnPlan(
                    name=technical_name,
                    source_column=fact.expr,
                    data_type=map_data_type(fact.data_type),
                    description=fact.description,
                    is_hidden=True,
                )
            )
            mapping[fact.expr.upper()] = technical_name
            if fact.default_aggregation:
                aggregation = fact.default_aggregation.upper()
                if aggregation != "SUM":
                    plan.diagnostics.append(
                        Diagnostic(
                            "warning",
                            "unsupported_default_aggregation",
                            f"Default aggregation '{aggregation}' is not supported.",
                            fact.name,
                        )
                    )
                else:
                    table.measures.append(
                        MeasurePlan(
                            name=fact.name,
                            expression=f"SUM('{table.name}'[{technical_name}])",
                            format_string=_measure_format(fact.name, fact.expr),
                            description=fact.description,
                            display_folder="Facts",
                            synonyms=tuple(fact.synonyms),
                        )
                    )
        for metric in source_table.metrics:
            try:
                metric_columns = referenced_columns(metric.expr)
            except ValueError as error:
                plan.diagnostics.append(
                    Diagnostic(
                        "warning",
                        "unsupported_metric_expression",
                        str(error),
                        metric.name,
                    )
                )
                continue
            for source_column in sorted(metric_columns):
                if source_column.upper() in mapping:
                    continue
                technical_name = f"__{source_column}"
                table.columns.append(
                    ColumnPlan(
                        name=technical_name,
                        source_column=source_column,
                        data_type="decimal",
                        description=f"Physical source column inferred from metric {metric.name}.",
                        is_hidden=True,
                    )
                )
                mapping[source_column.upper()] = technical_name
                plan.diagnostics.append(
                    Diagnostic(
                        "info",
                        "metric_source_column_inferred",
                        f"Imported undeclared metric source column '{source_column}' as decimal.",
                        metric.name,
                    )
                )
            try:
                dax = translate_metric(metric.expr, table.name, mapping)
            except (UnsupportedExpressionError, ValueError) as error:
                plan.diagnostics.append(
                    Diagnostic(
                        "warning",
                        "unsupported_metric_expression",
                        str(error),
                        metric.name,
                    )
                )
                continue
            table.measures.append(
                MeasurePlan(
                    name=metric.name,
                    expression=dax,
                    format_string=_measure_format(metric.name, metric.expr),
                    description=metric.description,
                    display_folder="Metrics",
                    synonyms=tuple(metric.synonyms),
                )
            )
            if metric.non_additive_dimensions:
                plan.diagnostics.append(
                    Diagnostic(
                        "warning",
                        "non_additive_metric_requires_review",
                        "The metric was converted, but its point-in-time behavior requires manual review.",
                        metric.name,
                    )
                )
        plan.tables.append(table)
        tables_by_name[table.name] = table
        source_mappings[table.name] = mapping

    for relationship in semantic_view.relationships:
        left = tables_by_name[relationship.left_table]
        right = tables_by_name[relationship.right_table]
        if len(relationship.relationship_columns) == 1:
            pair = relationship.relationship_columns[0]
            from_column = pair.left_column
            to_column = pair.right_column
        else:
            technical_name = f"__rel_{relationship.name}"
            left_columns = tuple(pair.left_column for pair in relationship.relationship_columns)
            right_columns = tuple(pair.right_column for pair in relationship.relationship_columns)
            left.composite_keys[technical_name] = left_columns
            right.composite_keys[technical_name] = right_columns
            left.columns.append(ColumnPlan(technical_name, technical_name, "string", is_hidden=True))
            right.columns.append(ColumnPlan(technical_name, technical_name, "string", is_hidden=True))
            from_column = technical_name
            to_column = technical_name
            plan.diagnostics.append(
                Diagnostic(
                    "info",
                    "composite_relationship_materialized",
                    "Composite relationship converted to a hidden Power Query key.",
                    relationship.name,
                )
            )
        plan.relationships.append(
            RelationshipPlan(
                name=relationship.name,
                from_table=left.name,
                from_column=from_column,
                to_table=right.name,
                to_column=to_column,
            )
        )

    return plan
