"""Generate Power Query M partitions for Snowflake Import tables."""

from __future__ import annotations

from smview2pbip.ir import TablePlan


def _m_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _m_column(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def render_partition(table: TablePlan) -> str:
    """Render an Import-mode Snowflake M query for one table."""

    physical_columns = [column.source_column for column in table.columns if not column.name.startswith("__rel_")]
    rename_pairs = [
        (column.source_column, column.name)
        for column in table.columns
        if not column.name.startswith("__rel_") and column.source_column != column.name
    ]
    selected = ", ".join(_m_string(name) for name in physical_columns)
    lines = [
        "let",
        "    Source = Snowflake.Databases(SnowflakeServer, SnowflakeWarehouse, [Role = SnowflakeRole]),",
        f"    Database = Source{{[Name = {_m_string(table.database)}]}}[Data],",
        f"    Schema = Database{{[Name = {_m_string(table.schema)}]}}[Data],",
        f"    SourceTable = Schema{{[Name = {_m_string(table.source_table)}]}}[Data],",
        f"    SelectedColumns = Table.SelectColumns(SourceTable, {{{selected}}})",
    ]
    previous_step = "SelectedColumns"
    if rename_pairs:
        pairs = ", ".join(
            "{" + _m_string(source) + ", " + _m_string(target) + "}"
            for source, target in rename_pairs
        )
        lines[-1] += ","
        lines.append(f"    RenamedColumns = Table.RenameColumns({previous_step}, {{{pairs}}})")
        previous_step = "RenamedColumns"
    key_items = list(table.composite_keys.items())
    for index, (key_name, columns) in enumerate(key_items, start=1):
        lines[-1] += ","
        values = ", ".join(_m_column(column) for column in columns)
        step_name = f"AddedRelationshipKey{index}"
        key_expression = (
            "Text.Combine(List.Transform({"
            + values
            + "}, each if _ = null then \"-1:\" else Text.From(Text.Length(Text.From(_))) "
            "& \":\" & Text.From(_)), \"|\")"
        )
        lines.append(
            f"    {step_name} = Table.AddColumn({previous_step}, {_m_string(key_name)}, "
            f"each {key_expression}, type text)"
        )
        previous_step = step_name
    lines.extend(["in", f"    {previous_step}"])
    return "\n".join(lines)
