# smview2pbip

`smview2pbip` converts Snowflake Semantic View YAML definitions into versionable Power BI
PBIP/TMDL projects in Import mode.

## Development status

The MVP validates a Snowflake Semantic View YAML file and generates:

- a local PBIP project with an Import-mode TMDL semantic model;
- parameterized Snowflake Power Query partitions;
- explicit DAX measures for supported `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`,
  `COUNT DISTINCT`, `COALESCE`, `ROUND`, `DIV0`, and arithmetic expressions;
- hidden technical keys for composite relationships;
- JSON and Markdown conversion reports;
- preserved source instructions and verified SQL queries for manual review.

## Validate a semantic view

```powershell
$env:PYTHONPATH = "src"
python -m smview2pbip.cli validate --input "path\to\semantic-view.yaml"
```

## Convert to PBIP

```powershell
$env:PYTHONPATH = "src"
python -m smview2pbip.cli convert `
	--input "path\to\semantic-view.yaml" `
	--output ".\generated" `
	--snowflake-server "organization-account.snowflakecomputing.com" `
	--snowflake-warehouse "ANALYTICS_WH" `
	--snowflake-role "POWER_BI_ROLE"
```

Credentials are never written to the generated project. Power BI requests authentication when
the model is refreshed.

Use `--strict` in CI to stop conversion when any metric requires manual review.

## Current limitations

- SQL-to-DAX conversion is intentionally limited to documented expression forms; unsupported or
	ambiguous expressions produce diagnostics and fail conversion with `--strict`.
- Point-in-time and semi-additive LTM metrics are flagged for manual review.
- Natural-language SQL generation instructions are preserved as documentation, not executed.
- Synonyms, translations, RLS/OLS, report visuals, and Fabric publication are outside this MVP.
- The generated project still requires validation in Power BI Desktop with a reachable Snowflake
	account before production use.