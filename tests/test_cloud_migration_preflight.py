import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "cloud_migration_preflight.py"


class CloudMigrationPreflightTests(unittest.TestCase):
    def run_preflight(self, backup):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "backup.json"
            source_path.write_text(json.dumps(backup), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TOOL), str(source_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        return result

    def test_valid_backup_reports_cloud_import_readiness_without_changing_ids(self):
        backup = {
            "format": "competitor-insights-backup",
            "version": 3,
            "exportedAt": "2026-07-31T00:00:00.000Z",
            "data": {
                "tabs": [
                    {
                        "id": "tab-1",
                        "name": "协同办公",
                        "competitors": [{"id": "competitor-1", "name": "竞品 A"}],
                        "evidenceItems": [
                            {
                                "id": "evidence-1",
                                "competitorId": "competitor-1",
                                "dimensionIds": ["dimension-1"],
                                "title": "功能证据",
                            }
                        ],
                        "insights": [{"id": "insight-1", "title": "研究洞察"}],
                        "comparisonData": {
                            "dimensions": [{"id": "dimension-1", "name": "核心能力"}],
                            "values": {"dimension-1": {"competitor-1": "已覆盖"}},
                        },
                    }
                ]
            },
        }

        result = self.run_preflight(backup)

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ready"])
        self.assertEqual(report["summary"], {
            "tabs": 1,
            "competitors": 1,
            "evidence": 1,
            "dimensions": 1,
            "insights": 1,
        })
        self.assertEqual(report["preservedIds"], {
            "tabs": ["tab-1"],
            "competitors": ["competitor-1"],
            "evidence": ["evidence-1"],
            "dimensions": ["dimension-1"],
            "insights": ["insight-1"],
        })
        self.assertEqual(report["issues"], [])

    def test_orphan_evidence_reference_blocks_cloud_import(self):
        backup = {
            "format": "competitor-insights-backup",
            "version": 3,
            "data": {
                "tabs": [
                    {
                        "id": "tab-1",
                        "name": "协同办公",
                        "competitors": [],
                        "evidenceItems": [
                            {
                                "id": "evidence-1",
                                "competitorId": "missing-competitor",
                                "dimensionIds": ["missing-dimension"],
                            }
                        ],
                        "insights": [],
                        "comparisonData": {"dimensions": [], "values": {}},
                    }
                ]
            },
        }

        result = self.run_preflight(backup)

        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertFalse(report["ready"])
        self.assertEqual(
            report["issues"],
            [
                "Tab“协同办公”的证据“evidence-1”关联了不存在的竞品“missing-competitor”。",
                "Tab“协同办公”的证据“evidence-1”关联了不存在的维度“missing-dimension”。",
            ],
        )


if __name__ == "__main__":
    unittest.main()
