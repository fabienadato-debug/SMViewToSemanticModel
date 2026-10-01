import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from smview2pbip.generators.dax import UnsupportedExpressionError, translate_metric
from smview2pbip.generators.pbip import write_pbip
from smview2pbip.planner import build_model_plan, map_data_type
from smview2pbip.reporting import write_conversion_reports
from smview2pbip.schema import load_semantic_view

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "SV_DWH_KPI_MOIS_GROUPE 9_30_2026, 10_34 AM.yaml"


class ConversionTests(unittest.TestCase):
    def test_maps_snowflake_types(self) -> None:
        self.assertEqual(map_data_type("VARCHAR(50)"), "string")
        self.assertEqual(map_data_type("NUMBER(22,8)"), "decimal")
        self.assertEqual(map_data_type("NUMBER(10,0)"), "int64")

    def test_translates_ratio_metric(self) -> None:
        dax = translate_metric(
            "ROUND(DIV0(100*SUM(REVENUE), SUM(TARGET)), 1)",
            "Sales",
            {"REVENUE": "__Revenue", "TARGET": "__Target"},
        )
        self.assertIn("DIVIDE", dax)
        self.assertIn("SUM('Sales'[__Revenue])", dax)
        self.assertIn("ROUND", dax)

    def test_translates_common_aggregate_functions(self) -> None:
        column_mapping = {"AMOUNT": "Amount", "CUSTOMER_ID": "Customer Id"}

        self.assertEqual(
            translate_metric("COUNT(*)", "Sales", column_mapping),
            "COUNTROWS('Sales')",
        )
        self.assertEqual(
            translate_metric("COUNT(CUSTOMER_ID)", "Sales", column_mapping),
            "COUNTAX('Sales', 'Sales'[Customer Id])",
        )
        self.assertEqual(
            translate_metric("COUNT(DISTINCT CUSTOMER_ID)", "Sales", column_mapping),
            "DISTINCTCOUNTNOBLANK('Sales'[Customer Id])",
        )
        self.assertEqual(
            translate_metric("AVG(AMOUNT)", "Sales", column_mapping),
            "AVERAGE('Sales'[Amount])",
        )
        self.assertEqual(
            translate_metric("MIN(AMOUNT)", "Sales", column_mapping),
            "MIN('Sales'[Amount])",
        )
        self.assertEqual(
            translate_metric("MAX(AMOUNT)", "Sales", column_mapping),
            "MAX('Sales'[Amount])",
        )

    def test_translates_coalesce(self) -> None:
        dax = translate_metric(
            "COALESCE(SUM(AMOUNT), 0)",
            "Sales",
            {"AMOUNT": "Amount"},
        )

        self.assertEqual(dax, "COALESCE(SUM('Sales'[Amount]), 0)")

    def test_rejects_complex_count_distinct(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedExpressionError,
            "COUNT DISTINCT is supported only for a single column",
        ):
            translate_metric(
                "COUNT(DISTINCT AMOUNT + CUSTOMER_ID)",
                "Sales",
                {"AMOUNT": "Amount", "CUSTOMER_ID": "Customer Id"},
            )

    def test_generates_pbip_from_real_yaml(self) -> None:
        plan = build_model_plan(load_semantic_view(FIXTURE))

        self.assertEqual(len(plan.tables), 7)
        self.assertEqual(len(plan.relationships), 6)
        self.assertEqual(sum(len(table.measures) for table in plan.tables), 33)
        self.assertEqual(
            len([item for item in plan.diagnostics if item.severity == "warning"]),
            1,
        )
        self.assertEqual(
            len([item for item in plan.diagnostics if item.code == "composite_relationship_materialized"]),
            4,
        )
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            pbip = write_pbip(plan, output, "SERVER", "WAREHOUSE", "ROLE")
            source = load_semantic_view(FIXTURE)
            write_conversion_reports(plan, source, output)
            definition = output / f"{plan.name}.SemanticModel" / "definition"

            self.assertTrue(pbip.is_file())
            self.assertTrue((definition / "model.tmdl").is_file())
            self.assertEqual(len(list((definition / "tables").glob("*.tmdl"))), 7)
            relationships = (definition / "relationships.tmdl").read_text(encoding="utf-8")
            self.assertIn("__rel_DWH_KPI_MOIS_GROUPE_DWH_UO", relationships)
            self.assertTrue((output / "conversion-report.json").is_file())
            self.assertTrue((output / "source-business-metadata.md").is_file())

    def test_generation_is_deterministic(self) -> None:
        source = load_semantic_view(FIXTURE)
        plan = build_model_plan(source)

        with TemporaryDirectory() as first_directory, TemporaryDirectory() as second_directory:
            first = Path(first_directory)
            second = Path(second_directory)
            for output in (first, second):
                write_pbip(plan, output, "SERVER", "WAREHOUSE", "ROLE")
                write_conversion_reports(plan, source, output)

            first_files = {
                path.relative_to(first): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)


if __name__ == "__main__":
    unittest.main()