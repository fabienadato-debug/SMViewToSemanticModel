import unittest
from pathlib import Path

from smview2pbip.schema import load_semantic_view

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "SV_DWH_KPI_MOIS_GROUPE 9_30_2026, 10_34 AM.yaml"


class SemanticViewSchemaTests(unittest.TestCase):
    def test_loads_real_semantic_view(self) -> None:
        semantic_view = load_semantic_view(FIXTURE)

        self.assertEqual(semantic_view.name, "SV_DWH_KPI_MOIS_GROUPE")
        self.assertEqual(len(semantic_view.tables), 7)
        self.assertEqual(len(semantic_view.relationships), 6)
        self.assertEqual(len(semantic_view.verified_queries), 4)


if __name__ == "__main__":
    unittest.main()
