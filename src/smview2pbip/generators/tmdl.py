"""Serialize a model plan as deterministic TMDL."""

from __future__ import annotations

from smview2pbip.generators.powerquery import render_partition
from smview2pbip.ir import ModelPlan, TablePlan


def quote_name(name: str) -> str:
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def _description(value: str | None) -> list[str]:
    if not value:
        return []
    return [f"/// {line}" for line in value.replace("\r", "").split("\n")]


def render_table(table: TablePlan) -> str:
    lines = [*_description(table.description), f"table {quote_name(table.name)}", ""]
    for measure in sorted(table.measures, key=lambda item: item.name):
        lines.extend(f"\t{line}" for line in _description(measure.description))
        lines.append(f"\tmeasure {quote_name(measure.name)} = {measure.expression}")
        lines.append(f"\t\tformatString: {measure.format_string}")
        lines.append(f"\t\tdisplayFolder: {quote_name(measure.display_folder)}")
        lines.append("")
    for column in table.columns:
        lines.extend(f"\t{line}" for line in _description(column.description))
        lines.append(f"\tcolumn {quote_name(column.name)}")
        lines.append(f"\t\tdataType: {column.data_type}")
        if column.is_hidden:
            lines.append("\t\tisHidden")
        lines.append("\t\tsummarizeBy: none")
        lines.append(f"\t\tsourceColumn: {quote_name(column.name)}")
        lines.append("")
    lines.append(f"\tpartition {quote_name(table.name)} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    lines.extend(f"\t\t\t{line}" for line in render_partition(table).splitlines())
    lines.append("")
    return "\n".join(lines)


def render_model(plan: ModelPlan) -> str:
    lines = [
        "model Model",
        f"\tculture: {plan.culture}",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        f"\tsourceQueryCulture: {plan.culture}",
        "\tdiscourageImplicitMeasures",
        "",
    ]
    lines.extend(f"ref table {quote_name(table.name)}" for table in plan.tables)
    lines.extend(
        [
            "",
            "ref expression SnowflakeServer",
            "ref expression SnowflakeWarehouse",
            "ref expression SnowflakeRole",
            "",
        ]
    )
    return "\n".join(lines)


def render_relationships(plan: ModelPlan) -> str:
    blocks: list[str] = []
    for relationship in plan.relationships:
        blocks.extend(
            [
                f"relationship {quote_name(relationship.name)}",
                f"\tfromColumn: {quote_name(relationship.from_table)}.{quote_name(relationship.from_column)}",
                f"\ttoColumn: {quote_name(relationship.to_table)}.{quote_name(relationship.to_column)}",
                "",
            ]
        )
    return "\n".join(blocks)


def render_expressions(server: str, warehouse: str, role: str) -> str:
    def parameter(name: str, value: str) -> str:
        escaped = value.replace('"', '""')
        return (
            f'expression {name} = "{escaped}" meta '
            "[IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]"
        )

    return "\n\n".join(
        [
            parameter("SnowflakeServer", server),
            parameter("SnowflakeWarehouse", warehouse),
            parameter("SnowflakeRole", role),
        ]
    ) + "\n"
