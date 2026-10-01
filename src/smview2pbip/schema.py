"""Pydantic models for the supported Snowflake Semantic View YAML surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SemanticViewModel(BaseModel):
    """Base model that preserves future Snowflake fields for diagnostics."""

    model_config = ConfigDict(extra="allow")


class BaseTable(SemanticViewModel):
    database: str
    schema_name: str = Field(alias="schema")
    table: str


class Column(SemanticViewModel):
    name: str
    expr: str
    data_type: str | None = None
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    access_modifier: str | None = None
    sample_values: list[Any] = Field(default_factory=list)


class NonAdditiveDimension(SemanticViewModel):
    table: str
    dimension: str
    sort_direction: str | None = None
    null_order: str | None = None


class Fact(Column):
    default_aggregation: str | None = None


class Metric(SemanticViewModel):
    name: str
    expr: str
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    access_modifier: str | None = None
    non_additive_dimensions: list[NonAdditiveDimension] = Field(default_factory=list)


class KeyDefinition(SemanticViewModel):
    columns: list[str]


class SemanticTable(SemanticViewModel):
    name: str
    base_table: BaseTable
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    primary_key: KeyDefinition | None = None
    unique_keys: list[KeyDefinition] = Field(default_factory=list)
    dimensions: list[Column] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)


class RelationshipColumn(SemanticViewModel):
    left_column: str
    right_column: str


class Relationship(SemanticViewModel):
    name: str
    left_table: str
    right_table: str
    relationship_columns: list[RelationshipColumn]
    relationship_type: str
    join_type: str | None = None


class VerifiedQuery(SemanticViewModel):
    name: str
    sql: str
    question: str
    verified_at: int | None = None
    verified_by: str | None = None
    use_as_onboarding_question: bool | None = None


class SemanticView(SemanticViewModel):
    name: str
    description: str | None = None
    tables: list[SemanticTable]
    relationships: list[Relationship] = Field(default_factory=list)
    module_custom_instructions: dict[str, str] = Field(default_factory=dict)
    verified_queries: list[VerifiedQuery] = Field(default_factory=list)


def load_semantic_view(path: Path) -> SemanticView:
    """Load and validate a Snowflake Semantic View YAML file."""

    with path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    return SemanticView.model_validate(payload)
