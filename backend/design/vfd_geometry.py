# -*- coding: utf-8 -*-
"""VFD 粘滞阻尼器 —— 结构图几何生成（样板版）

输入某规格的「基本尺寸」参数字典，输出统一的几何实体列表：
    · 前端用同一份数据画 SVG 预览
    · 后端转成 CSV 后走 csv_to_dxf 出 DXF

坐标约定
    X 轴：沿产品轴向，**前吊耳中心为原点 0**，向右为正
    Y 轴：径向，产品轴线为 0，上下对称
    单位：mm，1:1

主链（首尾闭合，合计 = 总长）
    0 -(前吊耳长)-> 前吊耳右侧边 -(前吊耳至前盖)-> 前盖前端面
    -(前盖厚度)-> 腔体起点 -(腔体长度)-> 腔体终点
    -(导向套定位长度)-> 导向套前端面 -(导向套台阶厚)-> 导向套后端面
    -(后缸筒长度)-> 后缸筒前端面 -(后盖台阶厚)-> 后缸筒后端面 -(后吊耳长)-> 后吊耳中心

    前盖厚度 = 前盖前面到前盖后面的距离，整段计入主链；
    前盖内部的台阶端、螺纹端仍按「前盖台阶厚」「前缸筒前后螺纹长度」绘制轮廓，
    但只作画图用的中间点，不再参与主链累计。

参数分三类：
    零件尺寸表  落盘在 data/vfd/缸径X，轴径Y/基本尺寸.csv，用户可改；
    输入参数    前端输入、不落盘，随请求注入（设计位移、腔体余量）；
    设计尺寸    不落盘，随型号与设计位移推导（见下方位移推导链与副链）。

位移推导链（设计位移为输入，其余为结果尺寸）
    极限位移 = 设计位移 × 1.5（< 100）；设计位移 × 1.2（≥ 100）
    前腔长 = 后腔长 = 极限位移 + 腔体余量
    腔体长度 = 前腔长 + 活塞宽 + 后腔长
    轴后端伸出长 = 前腔长 - 5
    轴后端到后盖距离 = 极限位移 + 25（M20×80 螺栓帽高）+ 10（余量）
    前吊耳至前盖 = 防尘罩长度核算（见 dust_cover_lug_distance）

副链（由台阶端 / 导向套后端面向后推导）
    前缸筒后端 = 导向套后端面 + 前缸筒前后螺纹长度；前缸筒长 = 前缸筒后端 - 台阶端
    锥形终点（轴后端面）= 导向套后端面 + 轴后端伸出长
    锥形起点 = 锥形终点 - 锥收口长；后段过渡终点 = 锥形终点 + 轴后端到后盖距离
    后缸筒长度 = 轴后端伸出长 + 轴后端到后盖距离 + 后盖螺纹长度
    轴的总长 = 锥形终点 - 轴端螺纹里端；安装距离 = 前吊耳中心至后吊耳中心

已接入：防尘罩（锯齿波纹）、图框（图幅贴合内容）、标题栏（内容可填）；
待补充：引出说明块、剖面线。
"""
import os
import csv
import math

# ---------------------------------------------------------------- 图层与样式

LAYER_OUTLINE = '粗实线层'
LAYER_THIN = '细实线层'
LAYER_CENTER = '中心线层'
LAYER_HIDDEN = '虚线层'
LAYER_DIM = '尺寸线层'
# 预览专用标注层：前腔/后腔长度、活塞宽度只在 SVG 预览中核对，
# 正式图纸不输出，故单独分层（DXF 的图层表里也不会出现）。
LAYER_PREVIEW_DIM = '预览尺寸层'

DIMSTYLE_NAME = 'CUSTOM_DIMSTYLE'

# 线型图案写成「数字分号串」，csv_to_dxf 会按元素长度求和补总长后建线型；
# 中文线型名会导致建线型失败退化为实线，因此这里用英文线型名 + 中文描述。
LAYER_DEFS = [
    {'name': '0', 'color': 7, 'linetype': 'Continuous', 'lineweight': -3, 'desc': '', 'pattern': ''},
    {'name': LAYER_CENTER, 'color': 1, 'linetype': 'CENTER', 'lineweight': 18, 'desc': '中心线', 'pattern': '12;-3;3;-3'},
    {'name': LAYER_HIDDEN, 'color': 6, 'linetype': 'DASHED', 'lineweight': 18, 'desc': '虚线', 'pattern': '6;-3'},
    {'name': LAYER_THIN, 'color': 7, 'linetype': 'Continuous', 'lineweight': 18, 'desc': '', 'pattern': ''},
    {'name': LAYER_OUTLINE, 'color': 7, 'linetype': 'Continuous', 'lineweight': 35, 'desc': '', 'pattern': ''},
    {'name': LAYER_DIM, 'color': 3, 'linetype': 'Continuous', 'lineweight': 18, 'desc': '', 'pattern': ''},
]

DIMSTYLE_DEFS = [
    ('Standard',
     '{"dimtxt": 2.5, "dimclrd": 0, "dimasz": 2.5, "dimtad": 1, "dimjust": 0, '
     '"dimlwd": -2, "dimexo": 0.625, "dimscale": 1.0, "dimalt": 0, '
     '"dimadec": 2, "dimdsep": 44}'),
    (DIMSTYLE_NAME,
     '{"dimtxt": 3.5, "dimclrd": 3, "dimasz": 3.0, "dimtad": 1, "dimjust": 0, '
     '"dimlwd": 0, "dimexo": 0.0, "dimscale": scale_factor, "dimalt": 0, '
     '"dimadec": 3, "dimdsep": 46}'),
]

CSV_HEADER = [
    '实体类型', '图层', '颜色', '线型', '线宽', '线型描述', '线型图案',
    '类型/名称', '块名', '值', '覆盖值',
    '位置 X', '位置 Y', '起点 X', '起点 Y', '终点 X', '终点 Y',
    '圆心 X', '圆心 Y', '半径', '顶点数据', '闭合', '高度', '角度',
    '尺寸编码', '起始角度', '终止角度', '缩放比例', '尺寸样式',
]

# 尺寸编码（与样张一致）
DIM_CODE_LINEAR = 32
DIM_CODE_RADIUS = 36

# 指引线注释文字高度（与产品图样张一致）
LEADER_TEXT_HEIGHT = 14.0


# ---------------------------------------------------------------- 小工具

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _fmt(value):
    """给 CSV 用的数值文本：整数不带小数点。"""
    f = float(value)
    if f == int(f):
        return str(int(f))
    return ('%.6f' % f).rstrip('0').rstrip('.')


class _Builder(object):
    """几何收集器：负责生成线段并自动镜像到轴线另一侧。"""

    def __init__(self):
        self.entities = []

    def line(self, x1, y1, x2, y2, layer=LAYER_OUTLINE):
        self.entities.append({
            'type': 'LINE', 'layer': layer,
            'start': (float(x1), float(y1)), 'end': (float(x2), float(y2)),
        })

    def sym_line(self, x1, y1, x2, y2, layer=LAYER_OUTLINE):
        """画一条线，并自动镜像到轴线另一侧。

        两种情形不需要再镜像（镜像线会与原线重合）：
          · 线本身落在轴线上（y 全为 0）
          · 线本身已上下对称（y1 == -y2，如整条竖直端面线）
        其余情形（含台阶处的短竖线、上下同号的斜线）都要镜像。
        """
        self.line(x1, y1, x2, y2, layer)
        if y1 == 0 and y2 == 0:
            return
        if abs(y1 + y2) < 1e-9:
            return
        self.line(x1, -y1, x2, -y2, layer)

    def arc(self, cx, cy, radius, start_angle, end_angle, layer=LAYER_OUTLINE):
        self.entities.append({
            'type': 'ARC', 'layer': layer,
            'center': (float(cx), float(cy)), 'radius': float(radius),
            'start_angle': float(start_angle), 'end_angle': float(end_angle),
        })

    def circle(self, cx, cy, radius, layer=LAYER_OUTLINE):
        self.entities.append({
            'type': 'CIRCLE', 'layer': layer,
            'center': (float(cx), float(cy)), 'radius': float(radius),
        })

    def linear_dim(self, value, p1, p2, location, angle=0.0, override='<>', layer=LAYER_DIM):
        """水平/垂直尺寸：p1、p2 为被测两点，location 为尺寸线位置。"""
        self.entities.append({
            'type': 'DIMENSION', 'layer': layer, 'dim_type': 'LINEAR',
            'value': float(value), 'override': override,
            'p1': (float(p1[0]), float(p1[1])), 'p2': (float(p2[0]), float(p2[1])),
            'location': (float(location[0]), float(location[1])),
            'angle': float(angle), 'dimstyle': DIMSTYLE_NAME,
        })

    def radius_dim(self, value, center, angle=0.0, location=None):
        self.entities.append({
            'type': 'DIMENSION', 'layer': LAYER_DIM, 'dim_type': 'RADIUS',
            'value': float(value), 'override': '',
            'center': (float(center[0]), float(center[1])),
            'location': (float(location[0]), float(location[1])) if location else (float(center[0]), float(center[1])),
            'angle': float(angle), 'dimstyle': DIMSTYLE_NAME,
        })

    def leader(self, points, text, text_pos, layer=LAYER_DIM):
        """指引线注释：折段引线（末段水平）+ 注释文字。

        points   折线各顶点，末段须水平
        text     注释文字
        text_pos 文字基线左端（位于末段上方）
        """
        for i in range(len(points) - 1):
            self.line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], layer)
        self.entities.append({
            'type': 'TEXT', 'layer': layer, 'text': str(text),
            'position': (float(text_pos[0]), float(text_pos[1])),
            'height': LEADER_TEXT_HEIGHT, 'rotation': 0.0,
        })

    def text(self, value, position, height, rotation=0.0, layer=LAYER_OUTLINE):
        """单行文字，position 为文字基线左端。"""
        self.entities.append({
            'type': 'TEXT', 'layer': layer, 'text': str(value),
            'position': (float(position[0]), float(position[1])),
            'height': float(height), 'rotation': float(rotation),
        })

    def mtext(self, value, position, height, rotation=0.0, layer=LAYER_OUTLINE,
              width_factor=0.7):
        """带格式文字，按样张格式 {\W宽度因子;\T行距;文字} 输出。

        plain / width_factor 供预览使用：预览不解析 MTEXT 控制码，直接用
        plain 显示文字，并按 width_factor 压缩字宽。
        """
        self.entities.append({
            'type': 'MTEXT', 'layer': layer,
            'text': '{\\W%s;\\T1.1;%s}' % (_fmt(width_factor), value),
            'plain': str(value), 'width_factor': float(width_factor),
            'position': (float(position[0]), float(position[1])),
            'height': float(height), 'rotation': float(rotation),
        })


# ---------------------------------------------------------------- 轴向特征点

# 防尘罩核算用的固定参数：只写入公式，不落盘到基本尺寸.csv。
# 依据「防尘罩长度计算.xlsx」的公式推导，含义见 dust_cover_lug_distance。
DUST_COVER_CLAMP = 15.0         # 防尘罩卡箍长
DUST_COVER_FLANGE = 3.0         # 防尘罩法兰厚
DUST_COVER_BOLT_HEAD = 10.0     # 螺栓头长度
DUST_COVER_CLEARANCE = 10.0     # 判断式中预留给螺栓头的安全余量

# 防尘罩外形尺寸（与产品图样张一致）
DUST_COVER_FLANGE_R = 65.0      # 右端法兰外半径
DUST_COVER_BELLOWS_R = 40.0     # 波纹段外半径
DUST_COVER_BELLOWS_INNER = 30.0 # 波纹段内沿半径（画虚线用）
DUST_COVER_CLAMP_OUT_R = 28.5   # 左端卡箍外半径
DUST_COVER_CLAMP_IN_R = 27.5    # 左端卡箍内半径
DUST_COVER_WAVE_PITCH = 15.0    # 波纹节距（一个波峰到下一个波峰的轴向距离）


def limit_displacement(design):
    """设计位移 -> 极限位移：小于 100 乘 1.5，否则乘 1.2。"""
    d = _num(design, 0.0)
    return d * 1.5 if d < 100 else d * 1.2


def dust_cover_lug_distance(limit):
    """前吊耳右侧边 → 前盖前端面（前吊耳设计距离）。

    由防尘罩最短压缩长度与安装空间共同约束，取满足条件的下限后
    就近圆整到末位 0 或 5；允许略微不足，由判断式中的螺栓头余量兜底。

    约束来源（防尘罩最长时被拉到极限、最短时被压到极限）：
        防尘罩最长长度 = 前吊耳设计距离 + 极限位移
        防尘罩最小长度 = (最长长度 - 卡箍长 - 法兰厚) / 10 + 卡箍长 + 法兰厚 + 螺栓头长度
        前吊耳最小距离 = 前吊耳设计距离 - 极限位移
        判断：前吊耳最小距离 - 螺栓头余量 > 防尘罩最小长度

    令 G 为前吊耳设计距离、Ld 为极限位移、H/I/J 为卡箍长/法兰厚/螺栓头长度，
    展开判断式（压缩比 1/10）：
        (G - Ld) - 10 > (G + Ld - H - I) / 10 + H + I + J
        9G > 11·Ld + 9H + 9I + 10J + 100
        G_min = (11·Ld + 9H + 9I + 10J + 100) / 9
    """
    ld = _num(limit, 0.0)
    h = DUST_COVER_CLAMP
    i = DUST_COVER_FLANGE
    j = DUST_COVER_BOLT_HEAD
    g_min = (11 * ld + 9 * h + 9 * i + 10 * j + 10 * DUST_COVER_CLEARANCE) / 9.0
    # 就近圆整到末位 0 或 5；用 floor(x + 0.5) 避免 round() 的银行家舍入
    return int(g_min / 5.0 + 0.5) * 5.0


# 可手工覆盖的设计尺寸：其余设计尺寸一律由推导链决定，不允许覆盖。
# 键名与前端 DERIVED_FIELDS 及 x[] 中的字段名保持一致。
# 前/后吊耳长默认取零件尺寸表里的值，允许在设计尺寸里覆盖。
OVERRIDABLE_KEYS = ('front_lug_length', 'lug_to_cover', 'rod_overhang', 'rod_to_rear_cover', 'rear_lug_length')


def _clean_overrides(overrides):
    """过滤覆盖值：只保留可覆盖的键且能被解析为数字的项。"""
    out = {}
    src = overrides or {}
    for key in OVERRIDABLE_KEYS:
        raw = src.get(key)
        if raw in (None, ''):
            continue
        try:
            out[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return out


def axial_points(p, overrides=None):
    """由零件尺寸推导全部轴向特征点（局部坐标，前吊耳中心 = 0）。

    overrides 为可覆盖设计尺寸的手工值（键见 OVERRIDABLE_KEYS）。
    某项一旦覆盖，该覆盖值取代其公式推导值，并参与其后所有下游计算，
    包括特征点位置、其余设计尺寸与预览图的显示。
    """
    g = lambda name, default=0.0: _num(p.get(name), default)
    ov = _clean_overrides(overrides)

    def o(key, computed):
        """取覆盖值；未启用覆盖时返回公式推导值。"""
        return ov[key] if key in ov else computed

    piston_w = g('活塞宽', 60)
    clearance = g('腔体余量', 30)
    limit = limit_displacement(g('设计位移', 60))
    chamber = limit + clearance                       # 前腔长 = 后腔长
    cavity_len = chamber * 2 + piston_w               # 腔体长度
    # 以下为可覆盖的设计尺寸；前/后吊耳长默认取零件尺寸表里的值
    front_lug_len = o('front_lug_length', g('前吊耳长', 120))     # 前吊耳长
    rear_lug_len = o('rear_lug_length', g('后吊耳长', 100))       # 后吊耳长
    lug_to_cover = o('lug_to_cover', dust_cover_lug_distance(limit))   # 前吊耳至前盖（防尘罩核算）
    rod_overhang = o('rod_overhang', chamber - 5)                 # 轴后端伸出长
    rod_to_rear_cover = o('rod_to_rear_cover', limit + 25 + 10)   # 轴后端到后盖距离（25 为 M20×80 螺栓帽高）
    # 后缸筒长度 = 轴后端伸出长 + 轴后端到后盖距离 + 后盖螺纹长度
    rear_barrel_len = rod_overhang + rod_to_rear_cover + g('后盖螺纹长度', 40)

    x = {
        'front_lug': 0.0,
    }
    x['lug_right'] = x['front_lug'] + front_lug_len
    # 轴端螺纹：自吊耳右侧边向左旋入，
    # thread_end 为螺纹里端，lug_right 为螺纹入口（吊耳右侧边）
    x['thread_end'] = x['lug_right'] - g('轴端螺纹长度', 55)
    x['cover_front'] = x['lug_right'] + lug_to_cover
    # 前盖厚度 = 前盖前面到前盖后面的距离，整段计入主链
    x['cavity_start'] = x['cover_front'] + g('前盖厚度', 65)
    # 前盖内部的台阶端、螺纹端仅作轮廓绘制用的中间点，不参与主链累计
    x['cover_step'] = x['cover_front'] + g('前盖台阶厚', 7)
    x['cover_thread_end'] = x['cover_step'] + g('前缸筒前后螺纹长度', 35)
    x['cavity_end'] = x['cavity_start'] + cavity_len
    x['guide_sleeve_front'] = x['cavity_end'] + g('导向套定位长度', 55)
    x['guide_sleeve_back'] = x['guide_sleeve_front'] + g('导向套台阶厚', 10)
    x['rear_barrel_front'] = x['guide_sleeve_back'] + rear_barrel_len
    x['rear_barrel_back'] = x['rear_barrel_front'] + g('后盖台阶厚', 10)
    x['rear_lug'] = x['rear_barrel_back'] + rear_lug_len

    # —— 结果尺寸（由上述特征点与位移推导链得出，不再作为输入）
    x['barrel_back'] = x['guide_sleeve_back'] + g('前缸筒前后螺纹长度', 35)
    x['taper_end'] = x['guide_sleeve_back'] + rod_overhang
    x['taper_start'] = x['taper_end'] - g('锥收口长', 4)
    x['rear_transition_end'] = x['taper_end'] + rod_to_rear_cover

    x['front_lug_length'] = front_lug_len                 # 前吊耳长
    x['rear_lug_length'] = rear_lug_len                   # 后吊耳长
    x['limit_displacement'] = limit
    x['chamber'] = chamber                                # 前腔长 = 后腔长
    x['cavity_length'] = cavity_len
    x['lug_to_cover'] = lug_to_cover                      # 前吊耳右侧边 → 前盖前端面
    x['rear_barrel_length'] = rear_barrel_len              # 导向套后端面 → 后缸筒前端面
    x['barrel_length'] = x['barrel_back'] - x['cover_step']          # 前缸筒长
    x['rod_overhang'] = rod_overhang                                 # 轴后端伸出长
    x['rod_to_rear_cover'] = rod_to_rear_cover                       # 轴后端到后盖距离
    x['rod_length'] = x['taper_end'] - x['thread_end']               # 轴的总长

    # 活塞体（居中于腔体）
    x['piston_center'] = (x['cavity_start'] + x['cavity_end']) / 2.0
    x['piston_left'] = x['piston_center'] - piston_w / 2.0
    x['piston_right'] = x['piston_center'] + piston_w / 2.0

    x['install_length'] = x['rear_lug'] - x['front_lug']             # 安装距离
    return x


def radial_values(p):
    """由零件尺寸取出全部径向值（半径）。

    除「吊耳半径」外，参数表里的径向尺寸一律按**直径**给出，
    这里统一除以 2 转成半径供几何使用。
    """
    g = lambda name, default=0.0: _num(p.get(name), default)
    d = lambda name, default=0.0: g(name, default) / 2.0
    return {
        'lug': g('吊耳半径', 62),
        'lug_width': g('吊耳宽度', 124),
        'bearing': d('轴承孔直径', 75),
        'pin': d('销轴孔直径', 50),
        'barrel_out': d('前缸筒外径', 168),
        'cover_bore': d('前缸筒前后螺纹直径', 150),
        'rod': d('活塞杆直径', 50),
        'piston': d('前缸筒内径', 140),
        'piston_body': d('活塞直径', 140),
        'rear_step': d('导向套直径', 145),
        'rear_cover': d('前缸筒前后螺纹直径', 150),
        'rear_inner': d('后缸筒内径', 132),
        'taper_end': d('锥收口末直径', 47),
        'rear_barrel_out': d('后缸筒外径', 162),
        'rear_barrel_in': d('后盖螺纹直径', 140),
    }


# ---------------------------------------------------------------- 轮廓

def build_outline(b, p, x, r):
    """生成结构图主轮廓（上下对称，镜像由 sym_line 负责）。"""
    # —— 前吊耳：左半圆弧 + 轴承孔 + 销轴孔 + 颈部
    b.arc(x['front_lug'], 0, r['lug'], 90, 270)
    b.circle(x['front_lug'], 0, r['bearing'])
    b.circle(x['front_lug'], 0, r['pin'])
    b.sym_line(x['front_lug'], r['lug'], x['lug_right'], r['lug'])
    # 前吊耳右侧边封板
    b.sym_line(x['lug_right'], r['lug'], x['lug_right'], -r['lug'])

    # —— 前吊耳至前盖之间的活塞杆（轴端螺纹旋入前吊耳，画成虚线）
    b.sym_line(x['thread_end'], r['rod'], x['lug_right'], r['rod'], layer=LAYER_HIDDEN)
    # 轴端螺纹里端封闭竖线
    b.sym_line(x['thread_end'], r['rod'], x['thread_end'], -r['rod'], layer=LAYER_HIDDEN)
    # 该段被防尘罩整体包覆，按制图惯例画成虚线
    b.sym_line(x['lug_right'], r['rod'], x['cover_front'], r['rod'], layer=LAYER_HIDDEN)

    # —— 前缸筒前端面 + 前盖台阶
    b.sym_line(x['cover_front'], r['barrel_out'], x['cover_front'], -r['barrel_out'])
    b.sym_line(x['cover_step'], r['barrel_out'], x['cover_step'], r['cover_bore'])
    b.sym_line(x['cover_step'], r['cover_bore'], x['cover_thread_end'], r['cover_bore'])

    # —— 前盖螺纹端 → 缸筒内孔
    b.sym_line(x['cover_thread_end'], r['cover_bore'], x['cover_thread_end'], r['piston'])
    b.sym_line(x['cover_thread_end'], r['piston'], x['guide_sleeve_front'], r['piston'])

    # —— 腔体段：两端面 + 体内轴肩
    b.sym_line(x['cavity_start'], r['piston'], x['cavity_start'], -r['piston'])
    b.sym_line(x['cavity_end'], r['piston'], x['cavity_end'], -r['piston'])
    b.sym_line(x['cavity_start'], r['rod'], x['cavity_end'], r['rod'])
    b.sym_line(x['piston_left'], r['piston_body'], x['piston_left'], r['rod'])
    b.sym_line(x['piston_right'], r['piston_body'], x['piston_right'], r['rod'])

    # —— 前缸筒外壁
    b.sym_line(x['cover_front'], r['barrel_out'], x['barrel_back'], r['barrel_out'])

    # —— 导向套
    b.sym_line(x['guide_sleeve_front'], r['rear_step'], x['guide_sleeve_front'], r['piston'])
    b.sym_line(x['guide_sleeve_front'], r['rear_step'], x['guide_sleeve_back'], r['rear_step'])
    b.sym_line(x['guide_sleeve_back'], r['rear_cover'], x['guide_sleeve_back'], -r['rear_cover'])
    b.sym_line(x['guide_sleeve_back'], r['rear_cover'], x['barrel_back'], r['rear_cover'])
    b.sym_line(x['barrel_back'], r['rear_cover'], x['barrel_back'], r['barrel_out'])

    # —— 后缸筒：活塞杆 + 后段内孔
    b.sym_line(x['guide_sleeve_back'], r['rod'], x['taper_start'], r['rod'])
    b.sym_line(x['guide_sleeve_back'], r['rear_inner'], x['rear_transition_end'], r['rear_inner'])

    # —— 锥收口
    b.sym_line(x['taper_start'], r['rod'], x['taper_start'], -r['rod'])
    b.sym_line(x['taper_start'], r['rod'], x['taper_end'], r['taper_end'])
    b.sym_line(x['taper_end'], r['taper_end'], x['taper_end'], -r['taper_end'])

    # —— 后缸筒外壁与后端面
    b.sym_line(x['barrel_back'], r['rear_barrel_out'], x['rear_barrel_back'], r['rear_barrel_out'])
    b.sym_line(x['rear_transition_end'], r['rear_barrel_in'], x['rear_transition_end'], -r['rear_barrel_in'])
    b.sym_line(x['rear_transition_end'], r['rear_barrel_in'], x['rear_barrel_front'], r['rear_barrel_in'])
    b.sym_line(x['rear_barrel_front'], r['rear_barrel_out'], x['rear_barrel_front'], -r['rear_barrel_out'])
    b.sym_line(x['rear_barrel_back'], r['rear_barrel_out'], x['rear_barrel_back'], -r['rear_barrel_out'])

    # —— 后吊耳：颈部 + 右半圆弧 + 轴承孔 + 销轴孔
    b.sym_line(x['rear_barrel_back'], r['lug'], x['rear_lug'], r['lug'])
    b.arc(x['rear_lug'], 0, r['lug'], 270, 90)
    b.circle(x['rear_lug'], 0, r['bearing'])
    b.circle(x['rear_lug'], 0, r['pin'])

    # —— 中心线
    b.line(x['front_lug'] - 62, 0, x['rear_lug'] + 62, 0, LAYER_CENTER)
    b.line(x['front_lug'], -75, x['front_lug'], 75, LAYER_CENTER)
    b.line(x['rear_lug'], -75, x['rear_lug'], 75, LAYER_CENTER)


def build_dust_cover(b, p, x, r):
    """防尘罩：右端法兰 + 波纹段（波浪线）+ 左端卡箍。

    轴向跨度 = 设计尺寸 lug_to_cover（前吊耳右侧边 → 前盖前端面），
    自右向左依次为：法兰厚 3 → 波纹段 → 卡箍长 15。
    右端面与前盖前端面平齐，左端面贴前吊耳右侧边。
    """
    right = x['cover_front']                       # 右端面（与前盖前端面平齐）
    left = x['lug_right']                          # 左端面（贴前吊耳右侧边）
    flange_left = right - DUST_COVER_FLANGE        # 法兰左端面 = 波纹段右端
    clamp_right = min(left + DUST_COVER_CLAMP, flange_left)   # 卡箍右端 = 波纹段左端

    # —— 右端法兰（外径 Ø130）
    b.sym_line(right, DUST_COVER_FLANGE_R, right, -DUST_COVER_FLANGE_R)
    b.sym_line(flange_left, DUST_COVER_FLANGE_R, flange_left, -DUST_COVER_FLANGE_R)
    b.sym_line(right, DUST_COVER_FLANGE_R, flange_left, DUST_COVER_FLANGE_R)

    # —— 波纹段：波峰（r40）与波谷（r30）之间往返的圆弧，即波浪线
    span = flange_left - clamp_right
    if span > 1e-6:
        amp = (DUST_COVER_BELLOWS_R - DUST_COVER_BELLOWS_INNER) / 2.0   # 波高（半幅）
        mid = (DUST_COVER_BELLOWS_R + DUST_COVER_BELLOWS_INNER) / 2.0   # 波纹的基线半径
        count = max(2, int(round(span / (DUST_COVER_WAVE_PITCH / 2.0))))
        step = span / count                                             # 一段圆弧的轴向跨度
        # 弦长为 step、矢高为 amp 的圆弧：半径 radius，圆心相对顶点的偏移 d
        radius = (step * step / 4.0 + amp * amp) / (2.0 * amp)
        d = radius - amp
        a_r = math.degrees(math.atan2(d, step / 2.0))                   # 端点角度（右）
        a_l = math.degrees(math.atan2(d, -step / 2.0))                  # 端点角度（左）
        for i in range(count):
            cx = clamp_right + (i + 0.5) * step
            if i % 2 == 0:          # 波峰朝外（顶点在 r40）
                c_y, a0, a1 = mid - d, a_r, a_l
            else:                   # 波谷朝内（顶点在 r30）
                c_y, a0, a1 = mid + d, a_r + 180.0, a_l + 180.0
            b.arc(cx, c_y, radius, a0 % 360.0, a1 % 360.0)
            b.arc(cx, -c_y, radius, (-a1) % 360.0, (-a0) % 360.0)
        # 相邻圆弧交接处：上侧交接点 → 下侧交接点 画竖线（跨过轴线，不镜像）
        for i in range(1, count):
            jx = clamp_right + i * step
            b.line(jx, mid, jx, -mid)
        # 波纹段与卡箍相接处封板
        b.sym_line(clamp_right, DUST_COVER_BELLOWS_R, clamp_right, -DUST_COVER_BELLOWS_R)

    # —— 左端卡箍（外径 Ø57 / 内径 Ø55）
    b.sym_line(clamp_right, DUST_COVER_CLAMP_OUT_R, left, DUST_COVER_CLAMP_OUT_R)
    b.sym_line(clamp_right, DUST_COVER_CLAMP_IN_R, left, DUST_COVER_CLAMP_IN_R)


# ---------------------------------------------------------------- 尺寸标注

def build_dimensions(b, p, x, r):
    """生成结构图尺寸标注（轴向链 + 位移链 + 关键直径 + 吊耳半径）。"""
    g = lambda name, default=0.0: _num(p.get(name), default)

    # 吊耳半径 R
    b.radius_dim(r['lug'], (x['front_lug'], 0), 142.314)
    b.radius_dim(r['lug'], (x['rear_lug'], 0), 31.969)

    # 前吊耳长（默认取零件尺寸，允许在设计尺寸里覆盖）
    b.linear_dim(x['front_lug_length'], (x['front_lug'], r['lug']), (x['lug_right'], r['lug']),
                 (x['front_lug'], 120))
    # 前吊耳至前盖（设计尺寸）
    b.linear_dim(x['lug_to_cover'], (x['lug_right'], r['lug']), (x['cover_front'], r['barrel_out']),
                 (x['lug_right'], 120))
    # 前缸筒长（结果尺寸）
    b.linear_dim(x['barrel_length'], (x['cover_step'], r['barrel_out']), (x['barrel_back'], r['barrel_out']),
                 (x['cover_step'], 142))
    # 后缸筒长度（设计尺寸）
    b.linear_dim(x['rear_barrel_length'], (x['guide_sleeve_back'], r['rear_inner']), (x['rear_barrel_front'], r['rear_barrel_out']),
                 (x['guide_sleeve_back'], 115))
    # 后吊耳长（默认取零件尺寸，允许在设计尺寸里覆盖）
    b.linear_dim(x['rear_lug_length'], (x['rear_barrel_back'], 0), (x['rear_lug'], 0),
                 (x['rear_barrel_back'], 115))
    # 轴后端伸出长（结果尺寸：导向套后端面 → 轴后端面）
    b.linear_dim(x['rod_overhang'], (x['guide_sleeve_back'], -30), (x['taper_end'], -r['taper_end']),
                 (x['guide_sleeve_back'], -50))
    # 轴后端到后盖距离（结果尺寸）
    b.linear_dim(x['rod_to_rear_cover'], (x['taper_end'], 16.923), (x['rear_transition_end'], 7.171),
                 (x['taper_end'], 40))
    # 轴的总长（结果尺寸：轴端螺纹里端 → 轴后端面）
    b.linear_dim(x['rod_length'], (x['thread_end'], -23), (x['taper_end'], -r['taper_end']),
                 (x['thread_end'], -143))
    # 安装距离（前吊耳中心 → 后吊耳中心，结果尺寸）
    b.linear_dim(x['install_length'], (x['front_lug'], -r['rear_cover']), (x['rear_lug'], -83),
                 (x['front_lug'], -175.807))

    # 直径：轴径（前吊耳与前盖之间）/ 缸筒内径（前腔）/ 缸筒外径（后腔）
    rod_dim_x = (x['lug_right'] + x['cover_front']) / 2.0
    b.linear_dim(2 * r['rod'], (rod_dim_x, -r['rod']), (rod_dim_x, r['rod']),
                 (rod_dim_x, -25), angle=90, override='%%%%C%s' % _fmt(2 * r['rod']))
    bore_dim_x = (x['cavity_start'] + x['piston_left']) / 2.0
    b.linear_dim(2 * r['piston'], (bore_dim_x, -r['piston']), (bore_dim_x, r['piston']),
                 (bore_dim_x, -70), angle=90, override='%%%%C%s' % _fmt(2 * r['piston']))
    out_dim_x = (x['piston_right'] + x['cavity_end']) / 2.0
    b.linear_dim(2 * r['barrel_out'], (out_dim_x, -r['barrel_out']), (out_dim_x, r['barrel_out']),
                 (out_dim_x, -84), angle=90, override='%%%%C%s' % _fmt(2 * r['barrel_out']))

    # 轴端螺纹长度（自吊耳右侧边起算）
    b.linear_dim(g('轴端螺纹长度'), (x['thread_end'], r['rod']), (x['lug_right'], r['rod']),
                 (x['thread_end'], 40))

    # 耳环厚度：垂直于图面方向，轮廓上量不到，按产品图做法用指引线引出注释
    note = '耳环厚度%s' % _fmt(g('耳环厚度', 60))
    gap = LEADER_TEXT_HEIGHT * 0.6          # 文字与水平引线的间距
    # 落点取吊耳圆弧上偏 45° 的位置，比轮廓最外极点靠里一点
    inset = r['lug'] / math.sqrt(2.0)
    # 前吊耳：自左侧圆弧向左上折，再水平向左伸出，文字在水平段上方
    lx = x['front_lug'] - inset + 25
    b.leader([(lx, inset), (lx - 45, 100), (lx - 150, 100)],
             note, (lx - 148, 100 + gap))
    # 后吊耳：自右侧圆弧向右上折，再水平向右伸出，文字在水平段上方
    rx = x['rear_lug'] + inset - 25
    b.leader([(rx, inset), (rx + 45, 100), (rx + 150, 100)],
             note, (rx + 43, 100 + gap))


def build_preview_dimensions(b, p, x, r):
    """预览专用标注：前腔长 / 活塞宽 / 后腔长。

    这三项只在 SVG 预览里供核对，正式图纸不输出，因此单独放在
    LAYER_PREVIEW_DIM 层，to_csv_rows 会把该层整体剔除。
    """
    piston_w = _num(p.get('活塞宽'), 60)
    y = 110.0
    b.linear_dim(x['piston_left'] - x['cavity_start'],
                 (x['cavity_start'], r['piston']), (x['piston_left'], r['piston']),
                 (x['cavity_start'], y), layer=LAYER_PREVIEW_DIM)
    b.linear_dim(piston_w,
                 (x['piston_left'], r['piston']), (x['piston_right'], r['piston']),
                 (x['piston_left'], y), layer=LAYER_PREVIEW_DIM)
    b.linear_dim(x['cavity_end'] - x['piston_right'],
                 (x['piston_right'], r['piston']), (x['cavity_end'], r['piston']),
                 (x['piston_right'], y), layer=LAYER_PREVIEW_DIM)


# ---------------------------------------------------------------- 图框与标题栏

FRAME_MARGIN = 25.0        # 内容与内框之间的最小边距
FRAME_UP_BIAS = 0.1        # 图形中心相对可用区中心上移的比例（× 可用区高度），图面更匀称
FRAME_GAP = 40.0           # 内框与外框的间距（与样张一致）
TITLE_W = 720.0            # 标题栏宽（与样张一致）
TITLE_H = 200.0            # 标题栏高（与样张一致）

# GB/T 14689 基本幅面的长宽比恒为 √2，加长幅面也沿用同一比例，
# 因此图幅不必查表：先定长边，再按比例算出短边即可。
SHEET_RATIO = math.sqrt(2.0)


def _sheet_size(need_w, need_h):
    """按标准长宽比（√2）算图幅，返回 (宽, 高)。

    取内容所需的长边作为图幅长边（向上取整到 1mm），短边由长边除以 √2
    得出，因此长宽比恒为标准值。
    """
    long_need, short_need = (need_w, need_h) if need_w >= need_h else (need_h, need_w)
    long_side = math.ceil(max(long_need, short_need * SHEET_RATIO))
    if need_w >= need_h:
        return float(long_side), long_side / SHEET_RATIO
    return long_side / SHEET_RATIO, float(long_side)

# 标题栏固定内容（与产品图样张一致）；项目名称/零件名称/产品型号/图纸编号/
# 数量由 title_info 传入，其余按样张固定。
TITLE_COMPANY = '羿射旭减隔震张家口有限公司'
TITLE_PART = '粘滞阻尼器'
TITLE_MATERIAL = ''
TITLE_WEIGHT = ''
TITLE_SCALE = '1:1'

# 标题栏框线（局部坐标：右下角为原点，x 向左为负，y 向上为正）
TITLE_LINES = [
    (-720, 200, 0, 200), (0, 200, 0, 0), (0, 0, -720, 0), (-720, 0, -720, 200),
    (-480, 0, -480, 200), (-240, 0, -240, 200),
    (-240, 60, -720, 60), (-240, 100, -720, 100),
    (-480, 180, -720, 180), (-480, 160, -720, 160), (-480, 140, -720, 140),
    (-480, 120, -720, 120), (-480, 80, -720, 80), (-480, 40, -720, 40),
    (-420, 20, -420, 100), (-360, 0, -360, 100), (-300, 20, -300, 100),
    (0, 150, -240, 150), (0, 100, -240, 100), (0, 50, -240, 50),
    (-684, 100, -684, 200), (-576, 100, -576, 200),
    (-600, 0, -600, 100), (-660, 0, -660, 100),
    (-648, 100, -648, 200), (-520, 100, -520, 200), (-540, 0, -540, 100),
    (-160, 0, -160, 200), (-720, 20, -240, 20),
]

# 标题栏表头文字（局部坐标，值固定）
# 每项为 (样张左端 x, y, 字高, 文字, 所在格子中心 x)
# 出图按样张左端 x 原样输出；预览可取格子中心 x 再居中（见 TITLE_CENTER_IN_PREVIEW）
TITLE_LABELS = [
    (-714, 118, 12, '标记', -702), (-678, 118, 12, '处数', -666),
    (-642, 118, 12, '更改文件名', -612), (-557, 118, 12, '签名', -548),
    (-508, 118, 12, '日期', -500),
    (-700, 97, 12, '设计', -690), (-700, 77, 12, '制图', -690), (-700, 58, 12, '审核', -690),
    (-464, 90, 14, '材料', -450), (-405, 89, 14, '数量', -390),
    (-345, 89, 14, '重量', -330), (-285, 89, 14, '比例', -270),
    (-232, 185, 16, '项目名称', -200), (-232, 135, 16, '零件名称', -200),
    (-232, 85, 16, '产品型号', -200), (-230, 35, 16, '图纸编号', -200),
    (-580, 96.31, 12, '日期', -570), (-580, 76.896, 12, '日期', -570),
    (-580, 56.696, 12, '日期', -570), (-580, 16.926, 12, '日期', -570),
    (-450, 13.806, 8, '第         页', -450), (-325, 14.229, 8, '共         页', -300),
]


def _text_width(value, height, width_factor=0.7):
    """估算文字宽度：全角按 1 个字高、半角按 0.5 个字高（× 宽度因子）。"""
    width = 0.0
    for ch in str(value):
        width += height * width_factor * (0.5 if ord(ch) < 0x2E80 else 1.0)
    return width


def _center_left(center_x, value, height, width_factor=0.7):
    """由格子中心 x 折算文字左端 x，使文字在格子里水平居中。"""
    return center_x - _text_width(value, height, width_factor) / 2.0


# 「项目名称」内容格：宽度 160，右侧格线在 0（见 TITLE_LINES 的 -160 竖线）
TITLE_PROJECT_CELL_W = 160.0
TITLE_PROJECT_PAD = 20.0        # 文字与格线之间保留的余量


# 估算字宽用的基准宽度（与 vfd_drawing.calculate_dynamic_width 一致）
TITLE_BASE_WIDTH_CN = 23.7
TITLE_BASE_WIDTH_EN = 11.85


def _fit_width(value, max_width):
    """按字数估算宽度，返回 (宽度因子, 实际宽度)。

    参考 vfd_drawing.calculate_dynamic_width：中文按 23.7、半角按 11.85 计宽，
    短文本保持样张宽度因子 0.7，字数多时按比例压缩（下限 0.3），使整串正好放进格内。
    """
    text = str(value)
    cn = sum(1 for ch in text if ord(ch) >= 0x2E80)
    en = len(text) - cn
    estimated = cn * TITLE_BASE_WIDTH_CN + en * TITLE_BASE_WIDTH_EN
    if estimated <= 0:
        return 0.7, 0.0
    factor = max(0.3, min(max_width / estimated, 0.7))
    return factor, estimated * factor


def title_info_of(project=None, model=None, drawing_no=None, part=None, quantity=None):
    """组装标题栏的可填字段，空值不输出（对应格子留空）。"""
    src = {
        'project': project, 'part': part, 'model': model, 'drawing_no': drawing_no,
        'quantity': quantity,
    }
    out = {}
    for key, value in src.items():
        text = str(value).strip() if value not in (None, '') else ''
        if text:
            out[key] = text
    return out


def _entities_bbox(entities):
    """全部实体的包围盒，返回 (min_x, min_y, max_x, max_y)。"""
    xs, ys = [], []
    for e in entities:
        t = e['type']
        if t == 'LINE':
            xs += [e['start'][0], e['end'][0]]
            ys += [e['start'][1], e['end'][1]]
        elif t in ('ARC', 'CIRCLE'):
            cx, cy = e['center']
            rr = e['radius']
            xs += [cx - rr, cx + rr]
            ys += [cy - rr, cy + rr]
        elif t in ('TEXT', 'MTEXT'):
            xs.append(e['position'][0])
            ys.append(e['position'][1])
        elif t == 'DIMENSION':
            pts = (e['p1'], e['p2'], e['location']) if e['dim_type'] == 'LINEAR' \
                else (e['center'], e['location'])
            for pt in pts:
                xs.append(pt[0])
                ys.append(pt[1])
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def build_title_block(b, ox, oy, info=None, center=False):
    """标题栏：右下角位于 (ox, oy)，固定 720×200。

    框线按样张绘制；表头与内容文字的字高、宽度因子照抄样张。
    center=False（出图）时 x 取样张左端值，与样张完全一致；
    center=True（预览）时 x 取所在格子中心，令文字在格子里水平居中。
    """
    info = info or {}
    for x1, y1, x2, y2 in TITLE_LINES:
        b.line(ox + x1, oy + y1, ox + x2, oy + y2, LAYER_OUTLINE)

    for lx, ly, height, value, cx in TITLE_LABELS:
        px = _center_left(cx, value, height) if center else lx
        b.mtext(value, (ox + px, oy + ly), height, layer=LAYER_OUTLINE)

    # 内容文字：(样张左端 x, y, 字高, 宽度因子, 值, 格子中心 x，是否自适应格宽)
    fills = [
        (-160, 185, 16, 0.7, info.get('project', 'XXX项目'), -80, True),
        (-120, 135, 16, 0.7, info.get('part', TITLE_PART), -80, False),
        (-125, 83, 16, 0.7, info.get('model', ''), -80, False),
        (-160, 35, 16, 0.7, info.get('drawing_no', ''), -80, False),
        (-476, 165, 20, 0.6, TITLE_COMPANY, -360, False),
        (-464, 50, 14, 0.7, TITLE_MATERIAL, -450, False),
        (-396, 50, 14, 0.7, info.get('quantity', ''), -390, False),
        (-345, 50, 14, 0.7, TITLE_WEIGHT, -330, False),
        (-285, 50, 14, 0.7, TITLE_SCALE, -270, False),
    ]
    for lx, ly, height, wf, value, cx, fit in fills:
        if not value:
            continue
        if fit:
            # 项目名称：按字数缩放字宽，使整串正好放进格子
            wf, length = _fit_width(value, TITLE_PROJECT_CELL_W - TITLE_PROJECT_PAD)
            if center:
                # 预览按实际渲染宽度（字高 × 宽度因子）居中，出图保持样张口径
                length = _text_width(value, height, wf)
            px = cx - length / 2.0
        else:
            px = _center_left(cx, value, height, wf) if center else lx
        b.mtext(value, (ox + px, oy + ly), height,
                layer=LAYER_OUTLINE, width_factor=wf)


def build_frame(b, entities, info=None, center_titles=False):
    """图框：外框按标准长宽比（√2）随内容定尺寸，标题栏贴内框右下角。

    先按内容算出所需图幅的长边，短边由 √2 换算，因此外框长宽比恒为标准值；
    内容在内框中居中摆放。
    """
    min_x, min_y, max_x, max_y = _entities_bbox(entities)
    content_w = max_x - min_x
    content_h = max_y - min_y
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    # 内框：图形 + 四周边距，下方再留出一条标题栏的高度
    inner_w = max(content_w + 2 * FRAME_MARGIN, TITLE_W + 2 * FRAME_MARGIN)
    inner_h = content_h + 2 * FRAME_MARGIN + TITLE_H

    # 外框：内框加装订/裁边间距后，按标准长宽比（√2）定图幅
    sheet_w, sheet_h = _sheet_size(inner_w + 2 * FRAME_GAP, inner_h + 2 * FRAME_GAP)

    inner_left = cx - sheet_w / 2.0 + FRAME_GAP
    inner_right = cx + sheet_w / 2.0 - FRAME_GAP

    # 可用区为「标题栏上沿 → 内框上沿」之间；图形在其中垂直居中后，
    # 再按可用区高度上移一点（图面上方留白略少、下方留给注释文字），比例随图幅缩放
    avail_h = (sheet_h - 2 * FRAME_GAP) - TITLE_H
    inner_bottom = cy - TITLE_H - avail_h / 2.0 - avail_h * FRAME_UP_BIAS
    inner_top = inner_bottom + sheet_h - 2 * FRAME_GAP

    outer_left = inner_left - FRAME_GAP
    outer_right = inner_right + FRAME_GAP
    outer_bottom = inner_bottom - FRAME_GAP
    outer_top = inner_top + FRAME_GAP

    for x1, y1, x2, y2 in (
        (outer_left, outer_bottom, outer_right, outer_bottom),
        (outer_right, outer_bottom, outer_right, outer_top),
        (outer_right, outer_top, outer_left, outer_top),
        (outer_left, outer_top, outer_left, outer_bottom),
    ):
        b.line(x1, y1, x2, y2, LAYER_THIN)

    for x1, y1, x2, y2 in (
        (inner_left, inner_bottom, inner_right, inner_bottom),
        (inner_right, inner_bottom, inner_right, inner_top),
        (inner_right, inner_top, inner_left, inner_top),
        (inner_left, inner_top, inner_left, inner_bottom),
    ):
        b.line(x1, y1, x2, y2, LAYER_OUTLINE)

    build_title_block(b, inner_right, inner_bottom, info, center=center_titles)


# ---------------------------------------------------------------- 对外接口

def build_geometry(params, overrides=None, preview_dims=False,
                   with_frame=False, title_info=None, center_titles=False):
    """参数 -> 几何实体列表（局部坐标，前吊耳中心为 0）。

    overrides     可覆盖设计尺寸的手工值，见 axial_points；
    preview_dims  为 True 时附加预览专用标注（前腔/后腔长度、活塞宽度）；
    with_frame    为 True 时在图形外围补图框与标题栏；
    title_info    标题栏可填字段（项目名称/零件名称/产品型号/图纸编号）；
    center_titles 仅预览用：标题栏文字按格子居中，出图保持样张左端位置。
    """
    p = params or {}
    x = axial_points(p, overrides)
    r = radial_values(p)

    b = _Builder()
    build_outline(b, p, x, r)
    build_dust_cover(b, p, x, r)
    build_dimensions(b, p, x, r)
    if preview_dims:
        build_preview_dimensions(b, p, x, r)
    if with_frame:
        build_frame(b, b.entities, title_info, center_titles=center_titles)
    return b.entities, x, r


def build_preview(params, overrides=None, title_info=None):
    """给前端 SVG 预览用的几何数据（含包围盒与特征点）。

    额外返回 axial_base：未应用覆盖的推导值，供前端在启用覆盖时
    显示被划掉的计算值。
    """
    p = params or {}
    ov = _clean_overrides(overrides)
    entities, x, r = build_geometry(p, ov, preview_dims=True,
                                    with_frame=True, title_info=title_info,
                                    center_titles=True)
    base = x if not ov else axial_points(p, None)

    xs, ys = [], []
    for e in entities:
        if e['type'] == 'LINE':
            xs += [e['start'][0], e['end'][0]]
            ys += [e['start'][1], e['end'][1]]
        elif e['type'] in ('ARC', 'CIRCLE'):
            cx, cy = e['center']
            rr = e['radius']
            xs += [cx - rr, cx + rr]
            ys += [cy - rr, cy + rr]
        elif e['type'] in ('TEXT', 'MTEXT'):
            xs += [e['position'][0]]
            ys += [e['position'][1]]
        elif e['type'] == 'DIMENSION' and e['layer'] == LAYER_PREVIEW_DIM:
            # 预览专用标注要计入包围盒，否则会被 viewBox 裁掉
            for pt in (e['p1'], e['p2'], e['location']):
                xs.append(pt[0])
                ys.append(pt[1])

    bbox = {
        'min_x': min(xs) if xs else 0.0,
        'min_y': min(ys) if ys else 0.0,
        'max_x': max(xs) if xs else 0.0,
        'max_y': max(ys) if ys else 0.0,
    }

    return {
        'entities': entities,
        'axial': x,
        'axial_base': base,
        'radial': r,
        'bbox': bbox,
        'layers': [d['name'] for d in LAYER_DEFS],
    }


def _blank_row():
    return {key: '' for key in CSV_HEADER}


def to_csv_rows(entities):
    """几何实体 -> csv_to_dxf 可识别的行（dict 列表）。"""
    rows = []

    # 图层定义行
    for d in LAYER_DEFS:
        row = _blank_row()
        row['实体类型'] = '图层'
        row['图层'] = d['name']
        row['颜色'] = str(d['color'])
        row['线型'] = d['linetype']
        row['线宽'] = str(d['lineweight'])
        row['线型描述'] = d['desc']
        row['线型图案'] = d['pattern']
        rows.append(row)

    # 实体行（预览专用标注层不落盘，正式图纸不输出）
    for e in entities:
        if e['layer'] == LAYER_PREVIEW_DIM:
            continue
        row = _blank_row()
        row['实体类型'] = e['type']
        row['图层'] = e['layer']
        row['颜色'] = 'BYLAYER'
        row['线型'] = 'BYLAYER'
        row['线宽'] = '-1'

        if e['type'] == 'LINE':
            row['起点 X'] = _fmt(e['start'][0])
            row['起点 Y'] = _fmt(e['start'][1])
            row['终点 X'] = _fmt(e['end'][0])
            row['终点 Y'] = _fmt(e['end'][1])
        elif e['type'] == 'CIRCLE':
            row['圆心 X'] = _fmt(e['center'][0])
            row['圆心 Y'] = _fmt(e['center'][1])
            row['半径'] = _fmt(e['radius'])
        elif e['type'] == 'ARC':
            row['圆心 X'] = _fmt(e['center'][0])
            row['圆心 Y'] = _fmt(e['center'][1])
            row['半径'] = _fmt(e['radius'])
            row['起始角度'] = _fmt(e['start_angle'])
            row['终止角度'] = _fmt(e['end_angle'])
        elif e['type'] in ('TEXT', 'MTEXT'):
            row['值'] = e['text']
            row['高度'] = _fmt(e.get('height', LEADER_TEXT_HEIGHT))
            row['角度'] = _fmt(e.get('rotation', 0.0))
            row['位置 X'] = _fmt(e['position'][0])
            row['位置 Y'] = _fmt(e['position'][1])
        elif e['type'] == 'DIMENSION':
            row['类型/名称'] = e['dim_type']
            row['值'] = _fmt(e['value'])
            row['覆盖值'] = e.get('override', '')
            row['位置 X'] = _fmt(e['location'][0])
            row['位置 Y'] = _fmt(e['location'][1])
            if e['dim_type'] == 'LINEAR':
                row['起点 X'] = _fmt(e['p1'][0])
                row['起点 Y'] = _fmt(e['p1'][1])
                row['终点 X'] = _fmt(e['p2'][0])
                row['终点 Y'] = _fmt(e['p2'][1])
                row['尺寸编码'] = str(DIM_CODE_LINEAR)
            else:
                row['圆心 X'] = _fmt(e['center'][0])
                row['圆心 Y'] = _fmt(e['center'][1])
                row['尺寸编码'] = str(DIM_CODE_RADIUS)
            row['角度'] = _fmt(e['angle'])
            row['尺寸样式'] = e.get('dimstyle', DIMSTYLE_NAME)
        rows.append(row)

    # 标注样式定义行（csv_to_dxf 会 eval 其中的 JSON）
    for name, attribs in DIMSTYLE_DEFS:
        row = _blank_row()
        row['实体类型'] = 'dimstyle'
        row['类型/名称'] = name
        row['值'] = attribs
        rows.append(row)

    return rows


def write_csv(entities, output_file):
    """把几何实体写成 csv_to_dxf 可读取的 CSV 文件。"""
    rows = to_csv_rows(entities)
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_file