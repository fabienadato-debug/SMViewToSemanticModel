"""Intermediate representation shared by the conversion stages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    object_name: str | None = None


@dataclass(frozen=True)
class ColumnPlan:
    name: str
    source_column: str
    data_type: str
    description: str | None = None
    is_hidden: bool = False
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class MeasurePlan:
    name: str
    expression: str
    format_string: str
    description: str | None = None
    display_folder: str = "Measures"
    synonyms: tuple[str, ...] = ()


@dataclass
class TablePlan:
    name: str
    database: str
    schema: str
    source_table: str
    description: str | None = None
    columns: list[ColumnPlan] = field(default_factory=list)
    measures: list[MeasurePlan] = field(default_factory=list)
    composite_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipPlan:
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str


@dataclass
class ModelPlan:
    name: str
    culture: str
    tables: list[TablePlan] = field(default_factory=list)
    relationships: list[RelationshipPlan] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
