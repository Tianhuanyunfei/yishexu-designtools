# -*- coding: utf-8 -*-
"""
解析 BRB 生产任务书 Excel（固定格式）。

仅识别标题为「生产任务书」的工作表；其它页忽略。
产品型号形如 BRB-{屈服力}-{长度}，数量在「数量」列。
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import load_workbook

BRB_MODEL_RE = re.compile(
    r"^\s*BRB\s*[-–—_]?\s*(\d+)\s*[-–—_]?\s*(\d+)\s*$",
    re.IGNORECASE,
)
TASKBOOK_TITLE = "生产任务书"


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _find_taskbook_sheet(wb):
    """
    仅识别标题含「生产任务书」的工作表；其它页一律忽略。
    若多页都有该标题，取工作簿中第一个匹配页。
    """
    for ws in wb.worksheets:
        # 只看首行是否为任务书标题
        for col in range(1, min(8, (ws.max_column or 1) + 1)):
            title = _cell_str(ws.cell(1, col).value)
            if title == TASKBOOK_TITLE or title.startswith(TASKBOOK_TITLE):
                return ws
    return None


def _extract_project_name(ws) -> str:
    """从「项目名称」标签右侧/下方取值。"""
    max_row = min(ws.max_row or 1, 20)
    max_col = min(ws.max_column or 1, 10)
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            label = _cell_str(ws.cell(row, col).value)
            if label == "项目名称" or label.startswith("项目名称"):
                right = _cell_str(ws.cell(row, col + 1).value)
                if right:
                    return right
                below = _cell_str(ws.cell(row + 1, col).value)
                if below and "项目" not in below:
                    return below
    return ""


def _find_product_header(ws) -> Optional[Tuple[int, int, int]]:
    """
    定位产品清单表头，返回 (header_row, model_col, qty_col)，列号 1-based。
    """
    max_row = min(ws.max_row or 1, 60)
    max_col = min(ws.max_column or 1, 15)
    for row in range(1, max_row + 1):
        model_col = None
        qty_col = None
        for col in range(1, max_col + 1):
            text = _cell_str(ws.cell(row, col).value)
            if text in ("型号", "产品型号", "规格型号"):
                model_col = col
            elif text in ("数量", "件数", "数量(件)"):
                qty_col = col
        if model_col and qty_col:
            return row, model_col, qty_col
    return None


def _parse_brb_model(text: str) -> Optional[Tuple[int, int]]:
    m = BRB_MODEL_RE.match(text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_brb_taskbook(file_path: str) -> Dict[str, Any]:
    """
    解析任务书，返回：
    {
      projectName, items: [{designForce, length, quantity, model}],
      parameterTables: [...前端可用参数表...],
      totalQuantity, skippedNonBrb, sheetName
    }
    """
    wb = load_workbook(file_path, data_only=True)
    ws = _find_taskbook_sheet(wb)
    if ws is None:
        raise ValueError('未找到标题为「生产任务书」的工作表，请确认上传的是生产任务书文件')

    project_name = _extract_project_name(ws)
    header = _find_product_header(ws)
    if header is None:
        raise ValueError('未找到产品清单表头（需要「型号」「数量」列）')

    header_row, model_col, qty_col = header
    items: List[Dict[str, Any]] = []
    skipped_non_brb: List[str] = []

    for row in range(header_row + 1, (ws.max_row or header_row) + 1):
        model = _cell_str(ws.cell(row, model_col).value)
        if not model:
            # 连续空行可结束；中间空行跳过
            continue
        # 表尾说明区
        if any(k in model for k in ("预埋件", "生产要求", "流程确认", "合计", "备注")):
            break

        parsed = _parse_brb_model(model)
        if not parsed:
            if model.upper().startswith("VFD") or "-" in model:
                skipped_non_brb.append(model)
            continue

        force, length = parsed
        qty = _to_int(ws.cell(row, qty_col).value)
        if qty is None or qty <= 0:
            continue

        items.append({
            "designForce": force,
            "length": length,
            "quantity": qty,
            "model": f"BRB-{force}-{length}",
        })

    if not items:
        raise ValueError("任务书中未解析到任何 BRB 产品（型号格式应为 BRB-屈服力-长度）")

    # 合并相同 力+长度
    merged: "OrderedDict[Tuple[int, int], int]" = OrderedDict()
    for it in items:
        key = (it["designForce"], it["length"])
        merged[key] = merged.get(key, 0) + it["quantity"]

    merged_items = [
        {
            "designForce": force,
            "length": length,
            "quantity": qty,
            "model": f"BRB-{force}-{length}",
        }
        for (force, length), qty in merged.items()
    ]

    # 按屈服力分组为参数表
    by_force: "OrderedDict[int, List[Dict[str, str]]]" = OrderedDict()
    for it in merged_items:
        force = it["designForce"]
        if force not in by_force:
            by_force[force] = []
        by_force[force].append({
            "length": str(it["length"]),
            "quantity": str(it["quantity"]),
        })

    parameter_tables = []
    base_id = int(__import__("time").time() * 1000)
    for i, (force, rows) in enumerate(by_force.items()):
        parameter_tables.append({
            "id": str(base_id + i) if i > 0 else "1",
            "designForce": str(force),
            "width": "",
            "height": "",
            "thickness": "",
            "tubeWidth": "",
            "tubeThickness": "",
            "weld": "",
            "coreMaterial": "Q235B",
            "template": "王（丨）",
            "lengthQuantityTable": rows,
        })

    total_quantity = sum(it["quantity"] for it in merged_items)

    return {
        "projectName": project_name,
        "sheetName": ws.title,
        "items": merged_items,
        "parameterTables": parameter_tables,
        "totalQuantity": total_quantity,
        "skippedNonBrb": skipped_non_brb,
        "brbCount": len(merged_items),
        "forceGroupCount": len(parameter_tables),
    }


if __name__ == "__main__":
    import json
    import os

    sample = os.path.join(
        os.path.dirname(__file__),
        "BRB-testdata",
        "生产任务单 - 产品.xlsx",
    )
    result = parse_brb_taskbook(sample)
    print(json.dumps(result, ensure_ascii=False, indent=2))
