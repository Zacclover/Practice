"""把竞品洞察台 v3 备份转换为云端工作区的规范化行。"""

from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5


# 输出结构：顺序与云端迁移时父表、关系表的写入顺序保持一致。
TABLE_NAMES = (
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
)

# 稳定主键：固定命名空间和规范化关系元组确保重复导入生成相同 UUID。
RELATION_ID_NAMESPACE = uuid5(
    NAMESPACE_URL, "competitor-insights/cloud-workspace-payload/v1"
)


def _relation_id(table_name: str, *values: Any) -> str:
    relationship_key = json.dumps(
        [table_name, *values],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return str(uuid5(RELATION_ID_NAMESPACE, relationship_key))


# v3 结构校验：只检查生成安全载荷所必需的容器，不改写业务数据。
def _validated_tabs(backup: Any) -> list[dict[str, Any]]:
    if not isinstance(backup, dict):
        raise ValueError("备份必须是对象。")
    if backup.get("format") != "competitor-insights-backup":
        raise ValueError("这不是竞品洞察台的有效备份文件。")
    if backup.get("version") != 3:
        raise ValueError("仅支持 competitor-insights-backup v3 备份。")

    data = backup.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("tabs"), list):
        raise ValueError("备份文件结构不完整。")
    if not data["tabs"]:
        raise ValueError("备份文件中没有可导入的 Tab。")
    if any(not isinstance(tab, dict) for tab in data["tabs"]):
        raise ValueError("Tab 的结构无效。")
    return data["tabs"]


# 集合读取：缺省集合按空列表处理，错误类型则拒绝以免静默丢失数据。
def _items(container: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = container.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} 必须是对象数组。")
    return value


# 公共字段映射：保留备份中的时间戳，缺省时交给数据库默认值生成。
def _with_common_fields(
    row: dict[str, Any], source: dict[str, Any], *, include_sample: bool = False
) -> dict[str, Any]:
    if include_sample:
        row["is_sample"] = source.get("isSample") is True
    if "createdAt" in source:
        row["created_at"] = source["createdAt"]
    if "updatedAt" in source:
        row["updated_at"] = source["updatedAt"]
    return row


# 工作区载荷生成：保留实体 ID，并把数组引用和矩阵对象拆成关系行。
def build_workspace_payload(
    backup: Any, workspace_id: str
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id 不能为空。")

    tabs = _validated_tabs(backup)
    payload: dict[str, list[dict[str, Any]]] = {
        table_name: [] for table_name in TABLE_NAMES
    }

    for tab_order, tab in enumerate(tabs):
        tab_id = tab.get("id")
        if not isinstance(tab_id, str) or not tab_id:
            raise ValueError("Tab id 不能为空。")

        tab_row = {
            "id": tab_id,
            "workspace_id": workspace_id,
            "name": tab.get("name", ""),
            "sort_order": tab_order,
        }
        payload["workspace_tabs"].append(_with_common_fields(tab_row, tab))

        # 竞品实体：字段名与 Supabase competitors 表保持一致。
        competitors = _items(tab, "competitors")
        for competitor in competitors:
            row = {
                "id": competitor.get("id"),
                "workspace_id": workspace_id,
                "tab_id": tab_id,
                "name": competitor.get("name", ""),
                "website": competitor.get("website", ""),
                "positioning": competitor.get("positioning", ""),
            }
            payload["competitors"].append(
                _with_common_fields(row, competitor, include_sample=True)
            )

        comparison = tab.get("comparisonData", {})
        if not isinstance(comparison, dict):
            raise ValueError("comparisonData 必须是对象。")

        # 维度实体：数组位置直接转换为稳定的数据库排序值。
        dimensions = _items(comparison, "dimensions")
        for dimension_order, dimension in enumerate(dimensions):
            row = {
                "id": dimension.get("id"),
                "workspace_id": workspace_id,
                "tab_id": tab_id,
                "name": dimension.get("name", ""),
                "sort_order": dimension_order,
            }
            payload["dimensions"].append(
                _with_common_fields(row, dimension, include_sample=True)
            )

        # 证据实体及证据维度关系：关系顺序沿用备份中的引用顺序。
        evidence_items = _items(tab, "evidenceItems")
        for evidence in evidence_items:
            evidence_id = evidence.get("id")
            row = {
                "id": evidence_id,
                "workspace_id": workspace_id,
                "tab_id": tab_id,
                "competitor_id": evidence.get("competitorId"),
                "title": evidence.get("title", ""),
                "content_html": evidence.get("contentHtml", ""),
                "images": evidence.get("images", []),
            }
            payload["evidence"].append(
                _with_common_fields(row, evidence, include_sample=True)
            )
            dimension_ids = evidence.get("dimensionIds", [])
            if not isinstance(dimension_ids, list):
                raise ValueError("dimensionIds 必须是数组。")
            payload["evidence_dimensions"].extend(
                {
                    "id": _relation_id(
                        "evidence_dimensions",
                        workspace_id,
                        tab_id,
                        evidence_id,
                        dimension_id,
                    ),
                    "workspace_id": workspace_id,
                    "tab_id": tab_id,
                    "evidence_id": evidence_id,
                    "dimension_id": dimension_id,
                }
                for dimension_id in dimension_ids
            )

        # 洞察实体及三类引用关系：只拆分引用，不生成或替换原始 ID。
        insights = _items(tab, "insights")
        for insight in insights:
            insight_id = insight.get("id")
            row = {
                "id": insight_id,
                "workspace_id": workspace_id,
                "tab_id": tab_id,
                "title": insight.get("title", ""),
                "fact_signals": insight.get("factSignals", ""),
                "common_pattern": insight.get("commonPattern", ""),
                "key_difference": insight.get("keyDifference", ""),
                "opportunity_hypothesis": insight.get("opportunityHypothesis", ""),
                "action_recommendation": insight.get("actionRecommendation", ""),
            }
            payload["insights"].append(
                _with_common_fields(row, insight, include_sample=True)
            )
            for source_field, table_name, target_field in (
                ("competitorIds", "insight_competitors", "competitor_id"),
                ("dimensionIds", "insight_dimensions", "dimension_id"),
                ("evidenceIds", "insight_evidence", "evidence_id"),
            ):
                reference_ids = insight.get(source_field, [])
                if not isinstance(reference_ids, list):
                    raise ValueError(f"{source_field} 必须是数组。")
                payload[table_name].extend(
                    {
                        "id": _relation_id(
                            table_name,
                            workspace_id,
                            tab_id,
                            insight_id,
                            reference_id,
                        ),
                        "workspace_id": workspace_id,
                        "tab_id": tab_id,
                        "insight_id": insight_id,
                        target_field: reference_id,
                    }
                    for reference_id in reference_ids
                )

        # 矩阵单元格：仅输出 values 中实际存在的格子，并合并示例标记。
        values = comparison.get("values", {})
        sample_values = comparison.get("sampleValues", {})
        if not isinstance(values, dict) or not isinstance(sample_values, dict):
            raise ValueError("矩阵 values 和 sampleValues 必须是对象。")
        for dimension_id, cells in values.items():
            if not isinstance(cells, dict):
                raise ValueError("矩阵维度值必须是对象。")
            samples = sample_values.get(dimension_id, {})
            samples = samples if isinstance(samples, dict) else {}
            for competitor_id, value in cells.items():
                payload["matrix_cells"].append(
                    {
                        "id": _relation_id(
                            "matrix_cells",
                            workspace_id,
                            tab_id,
                            dimension_id,
                            competitor_id,
                        ),
                        "workspace_id": workspace_id,
                        "tab_id": tab_id,
                        "dimension_id": dimension_id,
                        "competitor_id": competitor_id,
                        "value": value,
                        "is_sample": samples.get(competitor_id) is True,
                    }
                )

    return payload
