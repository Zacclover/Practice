#!/usr/bin/env python3
"""检查竞品洞察台 v3 备份能否安全导入云端。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# 报告初始化：固定云迁移预检输出结构，并保留遇到 ID 时的原始顺序。
def empty_report() -> dict[str, Any]:
    return {
        "ready": False,
        "summary": {
            "tabs": 0,
            "competitors": 0,
            "evidence": 0,
            "dimensions": 0,
            "insights": 0,
        },
        "preservedIds": {
            "tabs": [],
            "competitors": [],
            "evidence": [],
            "dimensions": [],
            "insights": [],
        },
        "issues": [],
    }


def object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def reference_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def display_id(item: dict[str, Any]) -> str:
    value = item.get("id")
    return value if isinstance(value, str) else str(value or "")


# Tab 关系校验：所有引用只能指向同一 Tab 内已经声明的数据实体。
def validate_tab_relationships(
    tab: dict[str, Any], tab_index: int, report: dict[str, Any]
) -> None:
    tab_name_value = tab.get("name")
    tab_name = (
        tab_name_value
        if isinstance(tab_name_value, str) and tab_name_value
        else f"洞察空间 {tab_index + 1}"
    )
    competitors = object_list(tab.get("competitors"))
    evidence_items = object_list(tab.get("evidenceItems"))
    insights = object_list(tab.get("insights"))
    comparison = tab.get("comparisonData")
    comparison = comparison if isinstance(comparison, dict) else {}
    dimensions = object_list(comparison.get("dimensions"))

    competitor_ids = {item.get("id") for item in competitors}
    evidence_ids = {item.get("id") for item in evidence_items}
    dimension_ids = {item.get("id") for item in dimensions}

    for evidence in evidence_items:
        evidence_id = display_id(evidence)
        competitor_id = evidence.get("competitorId")
        if competitor_id not in competitor_ids:
            report["issues"].append(
                f"Tab“{tab_name}”的证据“{evidence_id}”关联了不存在的竞品"
                f"“{competitor_id}”。"
            )
        for dimension_id in reference_list(evidence.get("dimensionIds")):
            if dimension_id not in dimension_ids:
                report["issues"].append(
                    f"Tab“{tab_name}”的证据“{evidence_id}”关联了不存在的维度"
                    f"“{dimension_id}”。"
                )

    for insight in insights:
        insight_id = display_id(insight)
        for competitor_id in reference_list(insight.get("competitorIds")):
            if competitor_id not in competitor_ids:
                report["issues"].append(
                    f"Tab“{tab_name}”的洞察“{insight_id}”关联了不存在的竞品"
                    f"“{competitor_id}”。"
                )
        for dimension_id in reference_list(insight.get("dimensionIds")):
            if dimension_id not in dimension_ids:
                report["issues"].append(
                    f"Tab“{tab_name}”的洞察“{insight_id}”关联了不存在的维度"
                    f"“{dimension_id}”。"
                )
        for evidence_id in reference_list(insight.get("evidenceIds")):
            if evidence_id not in evidence_ids:
                report["issues"].append(
                    f"Tab“{tab_name}”的洞察“{insight_id}”关联了不存在的证据"
                    f"“{evidence_id}”。"
                )

    for field_name, label in (("values", "矩阵值"), ("sampleValues", "示例标记")):
        rows = comparison.get(field_name)
        if not isinstance(rows, dict):
            continue
        for dimension_id, cells in rows.items():
            if dimension_id not in dimension_ids:
                report["issues"].append(
                    f"Tab“{tab_name}”的{label}关联了不存在的维度“{dimension_id}”。"
                )
            if not isinstance(cells, dict):
                continue
            for competitor_id in cells:
                if competitor_id not in competitor_ids:
                    report["issues"].append(
                        f"Tab“{tab_name}”的{label}在维度“{dimension_id}”下关联了"
                        f"不存在的竞品“{competitor_id}”。"
                    )


# v3 格式校验：拒绝旧版或结构不完整的备份，并汇总可迁移实体。
def inspect_backup(backup: Any) -> dict[str, Any]:
    report = empty_report()
    if not isinstance(backup, dict) or backup.get("format") != "competitor-insights-backup":
        report["issues"].append("这不是竞品洞察台的有效备份文件。")
        return report
    if backup.get("version") != 3:
        report["issues"].append("仅支持 competitor-insights-backup v3 备份。")
        return report
    data = backup.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("tabs"), list):
        report["issues"].append("备份文件结构不完整。")
        return report
    if not data["tabs"]:
        report["issues"].append("备份文件中没有可导入的 Tab。")
        return report

    tabs = data["tabs"]
    for index, tab in enumerate(tabs):
        if not isinstance(tab, dict):
            report["issues"].append(f"第 {index + 1} 个 Tab 的结构无效。")
            continue

        collections = {
            "competitors": object_list(tab.get("competitors")),
            "evidence": object_list(tab.get("evidenceItems")),
            "insights": object_list(tab.get("insights")),
        }
        comparison = tab.get("comparisonData")
        dimensions = object_list(
            comparison.get("dimensions") if isinstance(comparison, dict) else None
        )
        collections["dimensions"] = dimensions

        report["preservedIds"]["tabs"].append(display_id(tab))
        report["summary"]["tabs"] += 1
        for key, items in collections.items():
            report["summary"][key] += len(items)
            report["preservedIds"][key].extend(display_id(item) for item in items)

        validate_tab_relationships(tab, index, report)

    report["ready"] = not report["issues"]
    return report


# 命令行入口：只向标准输出写入一份 JSON 报告，阻塞导入时返回状态码 2。
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="competitor-insights-backup v3 JSON 文件")
    args = parser.parse_args()

    try:
        with args.backup.open("r", encoding="utf-8") as source:
            backup = json.load(source)
        report = inspect_backup(backup)
    except (OSError, UnicodeError, json.JSONDecodeError):
        report = empty_report()
        report["issues"].append("无法读取或解析备份文件。")

    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
