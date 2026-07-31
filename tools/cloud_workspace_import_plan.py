"""把云端工作区载荷转换为外键安全的显式写入批次。"""

from __future__ import annotations

from typing import Any

from tools.cloud_workspace_payload import TABLE_NAMES


# 写入顺序：父实体先于引用它们的实体和关系表。
INSERT_ORDER = TABLE_NAMES


# 导入计划生成：完整校验载荷表集合，并为每张表保留一个显式批次。
def build_workspace_import_plan(
    payload: Any, workspace_id: str
) -> list[dict[str, Any]]:
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id 不能为空。")
    if not isinstance(payload, dict):
        raise ValueError("工作区载荷必须是对象。")

    table_names = set(payload)
    expected_names = set(INSERT_ORDER)
    missing_names = expected_names - table_names
    unknown_names = table_names - expected_names
    if missing_names:
        raise ValueError(f"工作区载荷缺少表：{', '.join(sorted(missing_names))}。")
    if unknown_names:
        raise ValueError(f"工作区载荷包含未知表：{', '.join(sorted(unknown_names))}。")

    batches: list[dict[str, Any]] = []
    for table_name in INSERT_ORDER:
        rows = payload[table_name]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{table_name} 必须是对象数组。")
        batches.append(
            {
                "table": table_name,
                "workspace_id": workspace_id,
                "rows": list(rows),
            }
        )
    return batches
