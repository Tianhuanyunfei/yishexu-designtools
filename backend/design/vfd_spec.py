# -*- coding: utf-8 -*-
"""VFD 粘滞阻尼器 —— 数据层

四层数据架构中的第①、②层：

    ① 规格库    data/vfd/VFD-规格表.csv              缸径/轴径组合，由用户填写
    ② 基本尺寸   data/vfd/缸径X-轴径Y/基本尺寸.csv    结构图基准尺寸，用户改数值

本模块只负责读写，不含任何几何逻辑。
"""
import os
import csv

VFD_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'vfd')

SPEC_FILENAME = 'VFD-规格表.csv'
BASIC_FILENAME = '基本尺寸.csv'


def spec_dir(bore, axis):
    """该规格对应的数据目录：data/vfd/缸径140-轴径50"""
    return os.path.join(VFD_DATA_DIR, f'缸径{_num_text(bore)}-轴径{_num_text(axis)}')


def _num_text(value):
    """140.0 -> '140'，23.5 -> '23.5'"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if f == int(f):
        return str(int(f))
    return ('%g' % f)


def _parse_number(text, default=0.0):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def load_specs():
    """读取规格库。

    返回 [{'bore': 140, 'axis': 50}, ...]；同一缸径出现多行即代表该缸径有多个轴径。
    文件不存在时返回空列表，不抛异常。
    """
    path = os.path.join(VFD_DATA_DIR, SPEC_FILENAME)
    if not os.path.isfile(path):
        return []

    specs = []
    seen = set()
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            bore_text = (row.get('缸径') or '').strip()
            axis_text = (row.get('轴径') or '').strip()
            if not bore_text or not axis_text:
                continue
            key = (bore_text, axis_text)
            if key in seen:
                continue
            seen.add(key)
            specs.append({'bore': _parse_number(bore_text), 'axis': _parse_number(axis_text)})
    return specs


def load_basic_params(bore, axis):
    """读取某规格的零件尺寸表。

    表结构为「零件名, 尺寸名, 值, 说明」，同一零件名连续出现即为一组。
    返回 [{'part': '前/后吊耳', 'name': '前吊耳长', 'value': 120.0, 'note': '...'}, ...]，
    保持 CSV 中的书写顺序。
    """
    path = os.path.join(spec_dir(bore, axis), BASIC_FILENAME)
    if not os.path.isfile(path):
        return []

    params = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            name = (row.get('尺寸名') or '').strip()
            if not name:
                continue
            params.append({
                'part': (row.get('零件名') or '').strip(),
                'name': name,
                'value': _parse_number(row.get('值')),
                'note': (row.get('说明') or '').strip(),
            })
    return params


def save_basic_params(bore, axis, values):
    """按尺寸名覆盖零件尺寸表中的值，其余行原样保留。

    values: {'前吊耳长': 130, ...}，只更新出现的键。
    """
    path = os.path.join(spec_dir(bore, axis), BASIC_FILENAME)
    if not os.path.isfile(path):
        raise FileNotFoundError(f'零件尺寸表不存在: {path}')

    params = load_basic_params(bore, axis)
    for item in params:
        if item['name'] in values:
            item['value'] = _parse_number(values[item['name']], item['value'])

    text = '零件名,尺寸名,值,说明\n'
    for item in params:
        note = item['note'].replace(',', '，')
        text += f"{item['part']},{item['name']},{_num_text(item['value'])},{note}\n"

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return params


def params_to_dict(params):
    """[{'name','value'}] -> {'name': value}"""
    return {item['name']: item['value'] for item in params}
