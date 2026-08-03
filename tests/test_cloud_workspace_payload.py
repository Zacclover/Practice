import unittest
from uuid import UUID

from tools.cloud_workspace_payload import build_workspace_payload


class CloudWorkspacePayloadTests(unittest.TestCase):
    def test_maps_every_non_uuid_legacy_id_and_reference_consistently(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")

        ids = {
            table: payload[table][0]["id"]
            for table in ("workspace_tabs", "competitors", "dimensions", "evidence", "insights")
        }
        for mapped_id in ids.values():
            self.assertEqual(UUID(mapped_id).version, 5)

        self.assertEqual(payload["competitors"][0]["tab_id"], ids["workspace_tabs"])
        self.assertEqual(payload["evidence"][0]["competitor_id"], ids["competitors"])
        self.assertEqual(payload["evidence_dimensions"][0]["dimension_id"], ids["dimensions"])
        self.assertEqual(payload["insight_competitors"][0]["competitor_id"], ids["competitors"])
        self.assertEqual(payload["insight_dimensions"][0]["dimension_id"], ids["dimensions"])
        self.assertEqual(payload["insight_evidence"][0]["evidence_id"], ids["evidence"])
        self.assertEqual(payload["matrix_cells"][0]["dimension_id"], ids["dimensions"])
        self.assertEqual(payload["matrix_cells"][0]["competitor_id"], ids["competitors"])

    def test_rejects_dangling_legacy_references_instead_of_emitting_null_foreign_keys(self):
        backup = self._backup()
        backup["data"]["tabs"][0]["evidenceItems"][0]["competitorId"] = "missing"
        with self.assertRaisesRegex(ValueError, "未知 competitors 引用"):
            build_workspace_payload(backup, workspace_id="w-1")

    def test_keeps_ids_and_emits_parent_before_child_rows(self):
        backup = self._backup()
        payload = build_workspace_payload(backup, workspace_id="w-1")
        self.assertEqual(UUID(payload["workspace_tabs"][0]["id"]).version, 5)
        self.assertEqual(UUID(payload["competitors"][0]["id"]).version, 5)
        self.assertEqual(UUID(payload["dimensions"][0]["id"]).version, 5)
        self.assertEqual(UUID(payload["evidence"][0]["id"]).version, 5)
        self.assertEqual(payload["matrix_cells"][0]["value"], "支持")

    def test_relation_rows_match_migration_columns_and_have_uuid_ids(self):
        payload = build_workspace_payload(self._backup(), workspace_id="w-1")
        expected_relationships = {
            "evidence_dimensions": ("evidence_id", "dimension_id"),
            "insight_competitors": ("insight_id", "competitor_id"),
            "insight_dimensions": ("insight_id", "dimension_id"),
            "insight_evidence": ("insight_id", "evidence_id"),
        }

        for table_name, relationship in expected_relationships.items():
            row = payload[table_name][0]
            self.assertEqual(row["workspace_id"], "w-1")
            self.assertEqual(UUID(row["tab_id"]).version, 5)
            self.assertTrue(all(UUID(row[key]).version == 5 for key in relationship))
            self.assertEqual(UUID(row["id"]).version, 5)

    def test_relation_and_matrix_ids_are_deterministic_and_scoped(self):
        backup = self._backup()
        first = build_workspace_payload(backup, workspace_id="w-1")
        rerun = build_workspace_payload(backup, workspace_id="w-1")
        other_workspace = build_workspace_payload(backup, workspace_id="w-2")

        for table_name in (
            "evidence_dimensions",
            "insight_competitors",
            "insight_dimensions",
            "insight_evidence",
            "matrix_cells",
        ):
            first_id = first[table_name][0]["id"]
            self.assertEqual(first_id, rerun[table_name][0]["id"])
            self.assertNotEqual(first_id, other_workspace[table_name][0]["id"])
            self.assertEqual(UUID(first_id).version, 5)

        matrix_cell = first["matrix_cells"][0]
        self.assertEqual(matrix_cell["workspace_id"], "w-1")
        self.assertEqual(UUID(matrix_cell["tab_id"]).version, 5)
        self.assertEqual(UUID(matrix_cell["dimension_id"]).version, 5)
        self.assertEqual(UUID(matrix_cell["competitor_id"]).version, 5)

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
                        "competitors": [
                            {
                                "id": "c-1",
                                "name": "竞品",
                                "website": "https://example.com",
                                "positioning": "协作",
                            }
                        ],
                        "evidenceItems": [
                            {
                                "id": "e-1",
                                "competitorId": "c-1",
                                "dimensionIds": ["d-1"],
                                "title": "证据",
                                "contentHtml": "<p>正文</p>",
                                "images": [],
                                "createdAt": "2026-01-01T00:00:00Z",
                            }
                        ],
                        "insights": [
                            {
                                "id": "i-1",
                                "title": "洞察",
                                "competitorIds": ["c-1"],
                                "dimensionIds": ["d-1"],
                                "evidenceIds": ["e-1"],
                            }
                        ],
                        "comparisonData": {
                            "dimensions": [{"id": "d-1", "name": "能力"}],
                            "values": {"d-1": {"c-1": "支持"}},
                            "sampleValues": {},
                        },
                    }
                ]
            },
        }


if __name__ == "__main__":
    unittest.main()
