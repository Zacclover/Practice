import unittest

from tools.cloud_workspace_import_plan import (
    INSERT_ORDER,
    build_workspace_import_plan,
)
from tools.cloud_workspace_payload import build_workspace_payload


class CloudWorkspaceImportPlanTests(unittest.TestCase):
    def test_emits_explicit_batches_in_foreign_key_order(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")

        plan = build_workspace_import_plan(payload, workspace_id="w-1")

        self.assertEqual([batch["table"] for batch in plan], list(INSERT_ORDER))
        self.assertEqual(
            list(INSERT_ORDER),
            [
                "workspace_tabs",
                "competitors",
                "dimensions",
                "evidence",
                "evidence_dimensions",
                "insights",
                "insight_competitors",
                "insight_dimensions",
                "insight_evidence",
                "matrix_cells",
            ],
        )
        self.assertTrue(all(batch["workspace_id"] == "w-1" for batch in plan))
        self.assertEqual(
            {batch["table"]: batch["rows"] for batch in plan},
            payload,
        )

    def test_keeps_empty_tables_as_explicit_batches(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")
        self.assertEqual(payload["insight_evidence"], [])

        plan = build_workspace_import_plan(payload, workspace_id="w-1")

        insight_evidence = next(
            batch for batch in plan if batch["table"] == "insight_evidence"
        )
        self.assertEqual(insight_evidence["rows"], [])

    def test_rejects_missing_and_unknown_tables(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")
        missing = dict(payload)
        missing.pop("matrix_cells")
        unknown = {**payload, "workspace_members": []}

        with self.assertRaisesRegex(ValueError, "缺少表：matrix_cells"):
            build_workspace_import_plan(missing, workspace_id="w-1")
        with self.assertRaisesRegex(ValueError, "未知表：workspace_members"):
            build_workspace_import_plan(unknown, workspace_id="w-1")

    def test_rejects_empty_workspace_id(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")

        for workspace_id in ("", "   ", None):
            with self.subTest(workspace_id=workspace_id):
                with self.assertRaisesRegex(ValueError, "workspace_id 不能为空"):
                    build_workspace_import_plan(payload, workspace_id=workspace_id)

    @staticmethod
    def _backup():
        return {
            "format": "competitor-insights-backup",
            "version": 3,
            "data": {
                "tabs": [
                    {
                        "id": "tab-1",
                        "name": "研究",
                        "competitors": [{"id": "c-1", "name": "竞品"}],
                        "evidenceItems": [
                            {
                                "id": "e-1",
                                "competitorId": "c-1",
                                "dimensionIds": ["d-1"],
                                "title": "证据",
                            }
                        ],
                        "insights": [
                            {
                                "id": "i-1",
                                "competitorIds": ["c-1"],
                                "dimensionIds": ["d-1"],
                            }
                        ],
                        "comparisonData": {
                            "dimensions": [{"id": "d-1", "name": "能力"}],
                            "values": {"d-1": {"c-1": "支持"}},
                        },
                    }
                ]
            },
        }


if __name__ == "__main__":
    unittest.main()
