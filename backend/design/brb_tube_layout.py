import csv
import os
import sys
import copy
import json
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 配置参数
SPLICE_THRESHOLD = 600  # 余料拼接阈值，单位：mm

# 组合填充时优先规避的余料长度（mm）：实践中易被拼接链遗弃，在有多组「用料相同」的方案时让搜索偏向其它组合
#（典型：剩余净空约 10000 时 3500×2 余 3000，而 3300×3 余 100 更可接续）
DISCOURAGED_ORPHAN_LEFTOVERS = frozenset({3000})

# 末尾「段借出」修复（从其它方案挪小段填孤岛违规）。False 时输出段借出前的方案。
ENABLE_SEGMENT_BORROW_REPAIR = False

# 孤岛余料修复：后续原材上用余料拼接，实切 = 原长 − 孤岛余料（末根原材不再额外减 ORPHAN_TRIM_MM）。
ENABLE_ORPHAN_TRIM_REPAIR = True
ORPHAN_TRIM_MM = 50  # 仅当消费方为非末根原材时，实切再减此值（为同根上其它切段留缝）

# 孤岛整百拆分：无法直接拼接时，将余料拆成「整百可续接段 + 整百废料」（如 3800→3400+400）
ENABLE_ORPHAN_HUNDRED_SPLIT_REPAIR = True

# 择优评分：不低于此长度的未用余料视为「可跨项目复用库存」，不计入损耗比较
REUSABLE_LEFTOVER_SCORING_MIN_MM = 6000


def _leftover_pack_sort_key(leftover: int) -> Tuple[int, int]:
    """组合填充评分：先规避 DISCOURAGED_ORPHAN_LEFTOVERS，再最小化余料。"""
    if leftover < 0:
        return (99, leftover)
    risky = 1 if (leftover > SPLICE_THRESHOLD and leftover in DISCOURAGED_ORPHAN_LEFTOVERS) else 0
    return (risky, leftover)


def _reconstruct_take_cnt(bundles, prev, bundle_at, best_s) -> Dict[int, int]:
    take_cnt: Dict[int, int] = defaultdict(int)
    cur = best_s
    while cur > 0:
        bi = bundle_at[cur]
        if bi < 0:
            return {}
        _bw, L, ntake = bundles[bi]
        take_cnt[L] += ntake
        cur = prev[cur]
    return take_cnt


def _bounded_knapsack_pack_indices(
    remaining_tubes: List[dict],
    capacity: int,
    preferred_length_combos: Optional[set] = None,
) -> Tuple[List[int], int]:
    """
    在净空 capacity 内选自 remaining_tubes 的子集，使 _leftover_pack_sort_key(capacity - sum) 最小；
    并列键下优先用料更多（sum 更大）；再并列时偏好已出现过的长度组合（图面可合并）。
    管材仅按 tube_length 区分（同长 interchangeable）。

    返回：(按降序排列的下标列表，便于对 remaining_tubes 依次 pop)，以及选用的总长度。
    无可行非空子集时返回 ([], 0)。
    """
    if capacity <= 0 or not remaining_tubes:
        return [], 0

    preferred = preferred_length_combos or set()
    length_pools: Dict[int, List[int]] = defaultdict(list)
    for i, t in enumerate(remaining_tubes):
        length_pools[t['tube_length']].append(i)

    bundles: List[Tuple[int, int, int]] = []
    for L, idx_list in length_pools.items():
        cnt = len(idx_list)
        step = 1
        while cnt > 0:
            use = min(step, cnt)
            bundles.append((use * L, L, use))
            cnt -= use
            step *= 2

    W = capacity
    reachable = [False] * (W + 1)
    reachable[0] = True
    prev = [-1] * (W + 1)
    bundle_at = [-1] * (W + 1)

    for bi, (bw, _, _) in enumerate(bundles):
        for s in range(W, bw - 1, -1):
            if reachable[s - bw] and not reachable[s]:
                reachable[s] = True
                prev[s] = s - bw
                bundle_at[s] = bi

    best_s = 0
    best_cand: Optional[Tuple] = None
    for s in range(W + 1):
        if not reachable[s]:
            continue
        base = (_leftover_pack_sort_key(W - s), -s)
        if best_cand is not None and base > best_cand[:2]:
            continue
        prefer_penalty = 0
        if preferred:
            take_cnt = _reconstruct_take_cnt(bundles, prev, bundle_at, s)
            prefer_penalty = 0 if _length_combo_key(take_cnt) in preferred else 1
        cand = (*base, prefer_penalty)
        if best_cand is None or cand < best_cand:
            best_cand = cand
            best_s = s

    if best_s <= 0:
        return [], 0

    take_cnt = _reconstruct_take_cnt(bundles, prev, bundle_at, best_s)
    if not take_cnt:
        return [], 0

    indices_to_pop: List[int] = []
    for L, need in take_cnt.items():
        pool = length_pools[L]
        for _ in range(need):
            if not pool:
                return [], 0
            indices_to_pop.append(pool.pop())

    indices_to_pop.sort(reverse=True)
    return indices_to_pop, best_s


def _knapsack_pack_key_for_fill(capacity: int, used_sum: int, remaining_tubes: List[dict]) -> Tuple:
    """
    原材填充评分（越小越优）：
    0) 余料 <= 阈值；1) 余料可被下一根拼接；2) 其它（尽量用料多/余料小）。
    """
    leftover = capacity - used_sum
    if leftover <= SPLICE_THRESHOLD:
        return (0, leftover, -used_sum)
    if _can_splice_leftover_with_pool(leftover, remaining_tubes):
        return (1, leftover, -used_sum)
    return (2, leftover, -used_sum)


def _knapsack_pop_tubes_for_bar_fill(
    remaining_tubes: List[dict],
    capacity: int,
    preferred_length_combos: Optional[set] = None,
) -> Tuple[List[dict], int]:
    """
    在 capacity 内用有界背包选材并弹出，优先使余料 <= SPLICE_THRESHOLD，否则可拼接余料，否则余料最小。
    质量并列时偏好已出现过的长度组合。
    返回 (已选管材列表, 余料长度)。
    """
    if capacity <= 0 or not remaining_tubes:
        return [], capacity

    preferred = preferred_length_combos or set()
    length_pools: Dict[int, List[int]] = defaultdict(list)
    for i, t in enumerate(remaining_tubes):
        length_pools[t['tube_length']].append(i)

    bundles: List[Tuple[int, int, int]] = []
    for L, idx_list in length_pools.items():
        cnt = len(idx_list)
        step = 1
        while cnt > 0:
            use = min(step, cnt)
            bundles.append((use * L, L, use))
            cnt -= use
            step *= 2

    W = capacity
    reachable = [False] * (W + 1)
    reachable[0] = True
    prev = [-1] * (W + 1)
    bundle_at = [-1] * (W + 1)

    for bi, (bw, _, _) in enumerate(bundles):
        for s in range(W, bw - 1, -1):
            if reachable[s - bw] and not reachable[s]:
                reachable[s] = True
                prev[s] = s - bw
                bundle_at[s] = bi

    best_s = 0
    best_key = None
    for s in range(W + 1):
        if not reachable[s]:
            continue
        base = _knapsack_pack_key_for_fill(W, s, remaining_tubes)
        if best_key is not None and base > best_key[:len(base)]:
            continue
        prefer_penalty = 0
        if preferred:
            take_cnt = _reconstruct_take_cnt(bundles, prev, bundle_at, s)
            prefer_penalty = 0 if _length_combo_key(take_cnt) in preferred else 1
        cand = (*base, prefer_penalty)
        if best_key is None or cand < best_key:
            best_key = cand
            best_s = s

    if best_s <= 0:
        return [], capacity

    take_cnt = _reconstruct_take_cnt(bundles, prev, bundle_at, best_s)
    if not take_cnt:
        return [], capacity

    indices_to_pop: List[int] = []
    for L, need in take_cnt.items():
        pool = length_pools[L]
        for _ in range(need):
            if not pool:
                return [], capacity
            indices_to_pop.append(pool.pop())

    packed = []
    for idx in sorted(indices_to_pop, reverse=True):
        packed.append(remaining_tubes.pop(idx))
    packed.reverse()
    return packed, capacity - best_s


def is_no_splice_perfect_cut(plan, raw_length):
    """
    无拼接完美切割（与业务口径一致）：
    余料 ≤ SPLICE_THRESHOLD，且方案内无任何拼接段、无任何宿主/供给段、无对外续接。
    """
    lo = plan.get('remaining_length', raw_length)
    if lo > SPLICE_THRESHOLD:
        return False
    if (plan.get('splice_info') or {}).get('to_plan'):
        return False
    for t in plan.get('tubes', []):
        if 'spliced_from' in t:
            return False
        if t.get('host_role') in ('provider', 'host'):
            return False
    return True


def _plan_layout_signature(plan):
    """DXF 合并键（切割形态）：切段长度、拼接段、余料等。"""
    return (
        plan.get('tube_width'),
        plan.get('raw_length'),
        plan.get('remaining_length', 0),
        tuple((
            t.get('tube_length'),
            t.get('yield_force'),
            t.get('product_length'),
            t.get('spliced_from'),
            t.get('original_length'),
            t.get('nominal_tube_length'),
            t.get('host_role'),
            t.get('orphan_trim_mm'),
        ) for t in plan.get('tubes', [])),
    )


def _plan_model_signature(plan):
    """方案所属产品型号（按切段屈服力+产品长，有序元组）。"""
    return tuple(sorted(
        (t.get('yield_force'), t.get('product_length'))
        for t in plan.get('tubes', [])
    ))


def _plan_tubes_cut_tuple(plan):
    """切段几何元组（排序后，同多集合视为同刀型，便于图面合并）。"""
    return tuple(sorted(
        (
            t.get('tube_length'),
            t.get('yield_force'),
            t.get('product_length'),
            t.get('spliced_from'),
            t.get('original_length'),
            t.get('nominal_tube_length'),
            t.get('host_role'),
            t.get('orphan_trim_mm'),
        )
        for t in plan.get('tubes', [])
    ))


def _plan_dxf_cut_signature(plan):
    """DXF 图面合并键：同产品型号 + 同切割几何（切段顺序无关）。"""
    return (
        _plan_model_signature(plan),
        plan.get('tube_width'),
        plan.get('raw_length'),
        plan.get('remaining_length', 0),
        _plan_tubes_cut_tuple(plan),
    )


def _length_combo_key(combo_or_take_cnt) -> Tuple:
    """长度组合键：{length: count} → 有序元组，用于刀型同质偏好。"""
    if not combo_or_take_cnt:
        return tuple()
    return tuple(sorted((int(L), int(n)) for L, n in combo_or_take_cnt.items() if n))


def _plan_solid_length_combo(plan) -> Tuple:
    """方案中实切段（非拼接/宿主供给）的长度组合键。"""
    counts: Dict[int, int] = defaultdict(int)
    for t in plan.get('tubes', []) or []:
        if 'spliced_from' in t:
            continue
        if t.get('host_role') in ('provider', 'host'):
            continue
        L = t.get('tube_length')
        if L:
            counts[int(L)] += 1
    return _length_combo_key(counts)


def _tubes_solid_length_combo(tubes) -> Tuple:
    counts: Dict[int, int] = defaultdict(int)
    for t in tubes or []:
        if 'spliced_from' in t:
            continue
        if t.get('host_role') in ('provider', 'host'):
            continue
        L = t.get('tube_length')
        if L:
            counts[int(L)] += 1
    return _length_combo_key(counts)


def _count_dxf_merge_rows(plans) -> int:
    """合并后图面行数（越少图幅越短）。"""
    if not plans:
        return 0
    return len(_merge_plans_for_dxf(plans))


def _count_unique_cut_signatures(plans) -> int:
    """未合并前的唯一刀型数（含拼接方案各自签名）。"""
    if not plans:
        return 0
    return len({_plan_dxf_cut_signature(p) for p in plans})


def _plan_has_splice_relation(plan):
    # 宿主原材（host_provider_host）是独立刀型：K 整管 + 1 拼接段(R)，remaining_length=0，
    # 不承接余料也不外送余料。按普通方案合并(×N)，避免被并入拼接连通组而无法合并。
    if plan.get('perfect_source') == 'host_provider_host':
        return False
    si = plan.get('splice_info') or {}
    # provider 侧仅凭真实链关系(to_plan/from_plan)或承接段(spliced_from)判定为拼接组；
    # host_role 标记本身不再强制其进入连通组，使无续接的 provider 也可按刀型合并。
    return (
        any('spliced_from' in t for t in plan.get('tubes', []))
        or si.get('to_plan') is not None
        or si.get('from_plan') is not None
    )


def _dxf_row_is_pure_perfect(plan):
    """DXF 图面分组用：行内不含拼接段(spliced_from)也不含供段(provider)即为纯完美行。
    用于图面排序时把纯完美行排在含拼接/供段行之前，避免共用 plan_id 区间时交错。"""
    for t in plan.get('tubes', []):
        if 'spliced_from' in t or t.get('host_role') == 'provider':
            return False
    return True


def _find_splice_components(plans):
    """按 splice_info 前后指向划分拼接连通组（同宽度内）。"""
    plan_by_id = {p['plan_id']: p for p in plans if p.get('plan_id') is not None}
    relation_ids = {p['plan_id'] for p in plans if _plan_has_splice_relation(p) and p.get('plan_id') is not None}
    if not relation_ids:
        return []

    reverse_to = defaultdict(list)
    for p in plans:
        pid = p.get('plan_id')
        if pid not in relation_ids:
            continue
        to_plan = (p.get('splice_info') or {}).get('to_plan')
        if to_plan in relation_ids:
            reverse_to[to_plan].append(pid)

    visited = set()
    components = []
    for pid in sorted(relation_ids):
        if pid in visited:
            continue
        stack = [pid]
        comp_ids = set()
        while stack:
            cur = stack.pop()
            if cur in comp_ids:
                continue
            comp_ids.add(cur)
            cp = plan_by_id.get(cur)
            if not cp:
                continue
            to_plan = (cp.get('splice_info') or {}).get('to_plan')
            if to_plan in relation_ids:
                stack.append(to_plan)
            for prev in reverse_to.get(cur, []):
                stack.append(prev)
        visited.update(comp_ids)
        components.append([plan_by_id[i] for i in sorted(comp_ids)])
    return components


def _plan_splice_merge_context(plan, component_ids):
    """
    组内拼接角色（决定能否与别组合并）：
    - carry_in：本根首段承接的上一根余料长度
    - out_lo：本根尾余料（> 阈值）
    - to_offset：to_plan 相对本根的 plan_id 偏移（1=下一根，2=隔一根…）
    - back_out：本根末段是否反向消费下一根尾余（四段链原材 C → D 的 R0）
    """
    pid = plan.get('plan_id')
    si = plan.get('splice_info') or {}

    carry_in = None
    for t in plan.get('tubes', []):
        if 'spliced_from' in t and t.get('host_role') not in ('provider', 'host'):
            carry_in = t.get('spliced_from')
            break

    out_lo = plan.get('remaining_length', 0)
    out_lo_key = out_lo if out_lo > SPLICE_THRESHOLD else 0

    to_plan = si.get('to_plan')
    to_offset = None
    if to_plan is not None and pid is not None and to_plan in component_ids:
        to_offset = to_plan - pid

    back_out = None
    if out_lo > SPLICE_THRESHOLD:
        for t in plan.get('tubes', []):
            sf = t.get('spliced_from')
            if sf and sf == out_lo:
                back_out = sf
                break

    return (carry_in, out_lo_key, to_offset, back_out)


def _plan_role_signature(plan, component_ids):
    """拼接组内刀型 + 拼接上下文，用于识别周期内 repeating 角色。"""
    return (_plan_splice_merge_context(plan, component_ids), _plan_dxf_cut_signature(plan))


def _infer_periodic_cycle_count(role_counts):
    """
    推断完整周期重复次数：取出现 ≥2 次的角色里最少的那一档。
    例：128 根四段链 → 角色计数 8,8,7,7,1 → 周期数 7，多出的为收尾段。
    """
    repeating = [c for c in role_counts.values() if c >= 2]
    if not repeating:
        return max(role_counts.values()) if role_counts else 1
    return min(repeating)


def _tail_overflow_plan_ids(comp):
    """
    同一角色刀型若多于周期数，plan_id 最大的若干根视为收尾段，不与周期链合并。
    """
    sorted_comp = sorted(comp, key=lambda p: p.get('plan_id', 0))
    comp_ids = {p['plan_id'] for p in sorted_comp}
    role_of = {}
    sig_to_pids = defaultdict(list)
    for p in sorted_comp:
        sig = _plan_role_signature(p, comp_ids)
        role_of[p['plan_id']] = sig
        sig_to_pids[sig].append(p['plan_id'])

    cycle_count = _infer_periodic_cycle_count({s: len(v) for s, v in sig_to_pids.items()})
    tail_ids = set()
    for pids in sig_to_pids.values():
        if len(pids) > cycle_count:
            for pid in sorted(pids)[cycle_count:]:
                tail_ids.add(pid)
    return tail_ids


def _partition_splice_units(comp):
    """
    将拼接连通组拆成若干「完整拼接组合」：
    - 沿 to_plan 走链，to_plan 相对偏移为 2 时截断（四段链单周期）；
    - 无后继或余料不再接续时结束。
    """
    plan_by_id = {p['plan_id']: p for p in comp if p.get('plan_id') is not None}
    comp_ids = set(plan_by_id)
    if not comp_ids:
        return []

    incoming = set()
    for p in comp:
        to_plan = (p.get('splice_info') or {}).get('to_plan')
        if to_plan in comp_ids:
            incoming.add(to_plan)

    heads = sorted(
        (plan_by_id[i] for i in comp_ids if i not in incoming),
        key=lambda p: p.get('plan_id', 0),
    )
    if not heads:
        heads = [sorted(comp, key=lambda p: p.get('plan_id', 0))[0]]

    units = []
    visited = set()

    def _walk(start_id):
        unit = []
        cur = start_id
        local_seen = set()
        while cur in comp_ids:
            if cur in local_seen:
                break
            local_seen.add(cur)
            visited.add(cur)
            unit.append(plan_by_id[cur])
            cp = plan_by_id[cur]
            to_plan = (cp.get('splice_info') or {}).get('to_plan')
            if to_plan is None or to_plan not in comp_ids:
                break
            pid = cp.get('plan_id')
            if pid is not None and to_plan - pid == 2:
                break
            cur = to_plan
        return unit

    for h in heads:
        if h['plan_id'] in visited:
            continue
        u = _walk(h['plan_id'])
        if u:
            units.append(u)

    for pid in sorted(comp_ids):
        if pid not in visited:
            u = _walk(pid)
            if u:
                units.append(u)

    return units


def _splice_unit_is_tail(unit, tail_plan_ids):
    """收尾组合：含尾段角色和/或末根为大块未接续余料。"""
    if not unit:
        return False
    if any(p.get('plan_id') in tail_plan_ids for p in unit):
        return True
    last = unit[-1]
    si = last.get('splice_info') or {}
    if si.get('to_plan') is not None:
        return False
    return last.get('remaining_length', 0) >= REUSABLE_LEFTOVER_SCORING_MIN_MM


def _splice_unit_signature(unit, comp_ids, is_tail_unit):
    """完整拼接组合签名（有序刀型 + 各棒拼接上下文）。"""
    return (
        is_tail_unit,
        tuple(
            (_plan_splice_merge_context(p, comp_ids), _plan_dxf_cut_signature(p))
            for p in unit
        ),
    )


def _merge_plans_for_dxf(plans):
    """
    CAD 图面合并：
    1) 无拼接：同产品型号 + 同切割几何；
    2) 有拼接：仅合并「完整拼接组合」（整条链/单周期），显示 ×N 指 N 组相同组合；
    3) 周期链收尾段单独成组，不与完整周期合并。
    """
    plain_plans = [p for p in plans if not _plan_has_splice_relation(p)]
    relation_plans = [p for p in plans if _plan_has_splice_relation(p)]

    groups = {}
    splice_rows = []

    def _accumulate_plain(key, p):
        if key in groups:
            g = groups[key]
            g['raw_materials'] = g.get('raw_materials', 1) + p.get('raw_materials', 1)
            g['_merge_min_plan_id'] = min(
                g.get('_merge_min_plan_id', g.get('plan_id', 0)),
                p.get('plan_id', 0),
            )
        else:
            cp = copy.deepcopy(p)
            cp['_merge_min_plan_id'] = cp.get('plan_id', 0)
            cp['_dxf_is_splice_row'] = False
            cp['splice_info'] = {'from_plan': None, 'to_plan': None, 'length': 0}
            groups[key] = cp

    for p in plain_plans:
        _accumulate_plain(('plain', _plan_dxf_cut_signature(p)), p)

    unit_buckets = defaultdict(list)
    all_relation_ids = {p['plan_id'] for p in relation_plans if p.get('plan_id') is not None}
    for comp in _find_splice_components(relation_plans):
        tail_ids = _tail_overflow_plan_ids(comp) if len(comp) >= 3 else set()
        for unit in _partition_splice_units(comp):
            is_tail = _splice_unit_is_tail(unit, tail_ids)
            key = _splice_unit_signature(unit, all_relation_ids, is_tail)
            unit_buckets[key].append(unit)

    for unit_list in unit_buckets.values():
        combo_count = len(unit_list)
        template = sorted(unit_list[0], key=lambda p: p.get('plan_id', 0))
        combo_min_id = min(p.get('plan_id', 0) for p in template)
        for p in template:
            cp = copy.deepcopy(p)
            cp['_merge_min_plan_id'] = combo_min_id
            cp['_merge_combo_count'] = combo_count
            cp['raw_materials'] = combo_count
            cp['_dxf_is_splice_row'] = True
            cp['splice_info'] = {'from_plan': None, 'to_plan': None, 'length': 0}
            splice_rows.append(cp)

    merged = list(groups.values()) + splice_rows
    return sorted(
        merged,
        key=lambda x: x.get('_merge_min_plan_id', x.get('plan_id', 0)),
    )


def is_leftover_used_by_later_plan(plan, all_plans):
    """余料是否被后续方案的拼接段消费（与 DXF「余料总和」口径一致）。"""
    splice_info = plan.get('splice_info') or {}
    to_plan = splice_info.get('to_plan')
    if to_plan is None or to_plan <= 0:
        return False
    carry_len = splice_info.get('length', 0) or plan.get('remaining_length', 0)
    plan_width = plan.get('tube_width')
    for p in all_plans:
        if p.get('plan_id') != to_plan:
            continue
        if plan_width is not None and p.get('tube_width') != plan_width:
            continue
        for tube in p.get('tubes', []):
            sf = tube.get('spliced_from')
            if sf == carry_len or sf == plan.get('remaining_length', 0):
                return True
        break
    return False


def get_outbound_splice_carry(plan, all_plans):
    """
    本根尾端划给下一根、且未计入 remaining_length 的续接长度（mm）。
    整百拆分时 remaining 为废料、splice_info.length 为续接段（如 400+3400）；
    整段前送时 remaining 为 0、length 为整段余料。length 与 remaining 相同时返回 0，避免重复计量。
    """
    si = plan.get('splice_info') or {}
    carry_len = si.get('length', 0)
    if carry_len <= 0:
        return 0
    leftover = plan.get('remaining_length', 0)
    if carry_len == leftover and leftover > 0:
        return 0
    plan_width = plan.get('tube_width')
    to_plan = si.get('to_plan')
    if to_plan:
        targets = [p for p in all_plans if p.get('plan_id') == to_plan]
    else:
        pid = plan.get('plan_id', 0)
        targets = [
            p for p in all_plans
            if p.get('plan_id', 0) > pid
            and (plan_width is None or p.get('tube_width') == plan_width)
        ]
    for p in targets:
        if plan_width is not None and p.get('tube_width') != plan_width:
            continue
        for tube in p.get('tubes', []):
            if tube.get('spliced_from') == carry_len:
                return carry_len
    return 0


def format_plan_tail_segments(plan, all_plans):
    """
    方案预览尾段列表：切段之后用「 | 」分隔的余料/续接描述。
    例：余3400→#17 | 余400（整百拆分）；余600（纯废料）；余3500→#18（整段续接）。
    """
    parts = []
    leftover = plan.get('remaining_length', 0)
    si = plan.get('splice_info') or {}
    to_plan = si.get('to_plan')
    carry_out = get_outbound_splice_carry(plan, all_plans)

    if carry_out > 0 and to_plan:
        parts.append(f"余{carry_out}→#{to_plan}")

    if leftover > 0:
        if carry_out > 0 and carry_out != leftover:
            parts.append(f"余{leftover}")
        elif carry_out == 0:
            if leftover > SPLICE_THRESHOLD and to_plan and is_leftover_used_by_later_plan(plan, all_plans):
                parts.append(f"余{leftover}→#{to_plan}")
            else:
                parts.append(f"余{leftover}")

    return parts


def _resolve_stats_plan_for_dxf(draw_plan, stats_plans):
    """图面合并行 → 未合并方案（保留 splice_info，供续接段绘制）。"""
    # plan_id 仅在同宽度组内唯一（各宽度组独立从 1 编号），必须带 tube_width 对齐，
    # 否则多宽度项目会把 200 的 #9 误解析成 250 的 #9，导致假续接段与长度不闭合告警。
    draw_width = draw_plan.get('tube_width')

    def _width_ok(sp):
        return draw_width is None or sp.get('tube_width') == draw_width

    # 拼接组合内每行仍保留各自 plan_id，须优先按 plan_id 对齐（不能用组合 min_id 代替）
    pid = draw_plan.get('plan_id')
    if pid is not None:
        for sp in stats_plans:
            if sp.get('plan_id') == pid and _width_ok(sp):
                return sp
    min_id = draw_plan.get('_merge_min_plan_id')
    if min_id is not None:
        for sp in stats_plans:
            if sp.get('plan_id') == min_id and _width_ok(sp):
                return sp
    sig = _plan_dxf_cut_signature(draw_plan)
    for sp in stats_plans:
        if _width_ok(sp) and _plan_dxf_cut_signature(sp) == sig:
            return sp
    return draw_plan


def _sort_solid_segments_desc_for_display(plan):
    """
    将方案内「实体切段」按长度从长到短排序（图面与预览统一），不影响切割质量。
    拼接相关段（承接上一根余料的 spliced_from 段、宿主/供给段）保持原位不动，
    以免破坏拼接几何：承接段须留在原材左端衔接上一根尾料，
    续接段（carry_out）由 DXF 绘制逻辑单独追加在原材右端，亦不受影响。
    仅对实体切段按 tube_length 降序排序（稳定排序，同长保持原相对顺序），
    填回原实体段所在槽位；算法生成的切段顺序本身不一致，故用排序而非反转。
    """
    tubes = plan.get('tubes')
    if not tubes or len(tubes) < 2:
        return

    def _is_anchor(t):
        return ('spliced_from' in t) or (t.get('host_role') in ('host', 'provider'))

    solid_idx = [i for i, t in enumerate(tubes) if not _is_anchor(t)]
    if len(solid_idx) < 2:
        return
    solid_vals = [tubes[i] for i in solid_idx]
    sorted_vals = sorted(solid_vals, key=lambda t: t.get('tube_length') or 0, reverse=True)
    for i, val in zip(solid_idx, sorted_vals):
        tubes[i] = val


def sum_unused_leftover(plans):
    """
    未再使用的余料总和（mm）：各方案 remaining_length 累加，
    扣除已被下一方案 spliced_from 消费的中间余料；含 ≤ 阈值的尾料。
    """
    total = 0
    for plan in plans:
        if is_leftover_used_by_later_plan(plan, plans):
            continue
        total += plan.get('remaining_length', 0) * plan.get('raw_materials', 1)
    return total


def sum_scoring_waste(plans):
    """并联择优用余料：长料（可库存复用）不计入损耗比较。"""
    total = 0
    for plan in plans:
        if is_leftover_used_by_later_plan(plan, plans):
            continue
        r = plan.get('remaining_length', 0)
        if r >= REUSABLE_LEFTOVER_SCORING_MIN_MM:
            continue
        total += r * plan.get('raw_materials', 1)
    return total


def _leftover_can_splice_tube(leftover, tube_length):
    return (
        leftover > SPLICE_THRESHOLD
        and tube_length > leftover
        and (tube_length - leftover) > SPLICE_THRESHOLD
    )


def _can_splice_leftover_with_pool(leftover, remaining_tubes):
    if leftover <= SPLICE_THRESHOLD:
        return False
    return any(
        _leftover_can_splice_tube(leftover, t['tube_length'])
        for t in remaining_tubes
    )


def _consume_pending_leftovers(remaining_tubes, leftovers):
    """
    从待拼接余料队列中消费一段，返回 (拼接段列表, 更新后的 leftovers)。
    与 LegacyGreedy._apply_greedy_fill 开头逻辑一致。
    """
    if not leftovers or not remaining_tubes:
        return [], leftovers

    for i, leftover in enumerate(leftovers):
        if leftover <= SPLICE_THRESHOLD:
            continue
        for j, tube in enumerate(remaining_tubes):
            if not _leftover_can_splice_tube(leftover, tube['tube_length']):
                continue
            seg = {
                'tube_length': tube['tube_length'] - leftover,
                'product_length': tube['product_length'],
                'yield_force': tube['yield_force'],
                'tube_width': tube['tube_width'],
                'spliced_from': leftover,
                'original_length': tube['tube_length'],
            }
            remaining_tubes.pop(j)
            leftovers = leftovers[:i] + leftovers[i + 1:]
            return [seg], leftovers
    return [], leftovers


def prune_stale_splice_links(plans):
    """清除无实际消费方的 splice_info.to_plan（避免日志/图面误显「→#下一根」）。"""
    if not plans:
        return plans
    plans = copy.deepcopy(plans)
    by_width = {}
    for p in plans:
        by_width.setdefault(p.get('tube_width'), []).append(p)
    for group in by_width.values():
        for p in group:
            si = p.get('splice_info') or {}
            if si.get('to_plan') and not is_leftover_used_by_later_plan(p, group):
                si['to_plan'] = None
                if si.get('length') == p.get('remaining_length'):
                    si['length'] = 0
    return plans


def ensure_forward_splice_links(plans, raw_length):
    """
    排料收尾：非末根原材的大余料必须在下一根方案上已有拼接消费（避免「死余料」）。
    仅当下一根确实存在可拼接切段时才写入 to_plan。
    """
    if not plans:
        return plans

    plans = copy.deepcopy(plans)
    by_width = {}
    for p in plans:
        by_width.setdefault(p.get('tube_width'), []).append(p)

    for group in by_width.values():
        sorted_group = sorted(group, key=lambda x: x.get('plan_id', 0))
        if len(sorted_group) < 2:
            continue
        plan_by_id = {p['plan_id']: p for p in sorted_group}
        last_id = sorted_group[-1]['plan_id']

        for i, p in enumerate(sorted_group[:-1]):
            if p.get('plan_id') == last_id:
                continue
            leftover = p.get('remaining_length', 0)
            if leftover <= SPLICE_THRESHOLD:
                continue

            consumed = False
            to_plan = (p.get('splice_info') or {}).get('to_plan')
            if to_plan in plan_by_id:
                target = plan_by_id[to_plan]
                if any(t.get('spliced_from') == leftover for t in target.get('tubes', [])):
                    consumed = True
                elif any(t.get('host_role') == 'provider' for t in target.get('tubes', [])):
                    consumed = True

            if consumed:
                continue

            next_p = sorted_group[i + 1]
            splice_info = p.setdefault(
                'splice_info', {'from_plan': None, 'to_plan': None, 'length': 0}
            )

            for tube in next_p.get('tubes', []):
                if tube.get('host_role') in ('provider', 'host'):
                    continue
                if 'spliced_from' in tube:
                    continue
                nominal = tube['tube_length']
                if not _leftover_can_splice_tube(leftover, nominal):
                    continue
                splice_info['to_plan'] = next_p['plan_id']
                splice_info['length'] = leftover
                tube['spliced_from'] = leftover
                tube['tube_length'] = nominal - leftover
                tube['nominal_tube_length'] = nominal
                tube['original_length'] = nominal
                _refresh_plan_remaining(next_p, raw_length)
                logging.info(
                    "前向拼接：方案#%s 余料 %s -> 方案#%s 实切 %s",
                    p.get('plan_id'), leftover, next_p.get('plan_id'), tube['tube_length'],
                )
                break

        last_p = sorted_group[-1]
        last_si = last_p.get('splice_info')
        if last_si and last_si.get('to_plan') is not None:
            last_si['to_plan'] = None

    return prune_stale_splice_links(plans)


def sum_brb_tube_demand_length(plans, tube_width=None):
    """
    BRB 方管成品下料总长度（mm）：每根需求只计一次，不超过原材可切总量。

    - 普通段：tube_length（产品长 − 300）
    - 拼接段：nominal / original_length（实切 + 余料拼接，不重复计 provider 供给段）
    - host_role=provider：跳过（已计入对应拼接段的 spliced_from）
    """
    total = 0
    for plan in plans:
        if tube_width is not None and plan.get('tube_width') != tube_width:
            continue
        rm = plan.get('raw_materials', 1)
        for tube in plan.get('tubes', []):
            if tube.get('host_role') == 'provider':
                continue
            if 'spliced_from' in tube:
                seg_len = _nominal_tube_length(tube)
            else:
                seg_len = tube.get('tube_length', 0)
            total += seg_len * rm
    return total


def _plan_used_length(plan):
    return sum(t.get('tube_length', 0) for t in plan.get('tubes', []))


def _refresh_plan_remaining(plan, raw_length):
    plan['remaining_length'] = raw_length - _plan_used_length(plan)


def _nominal_tube_length(tube):
    return tube.get('nominal_tube_length') or tube.get('original_length') or tube.get('tube_length', 0)


def format_tube_dim_label(tube, use_full_splice_label=False, segment_index=0, first_sp_j=None, last_sp_j=None):
    """图面/日志中方管段长度标注（含孤岛减短后的原长说明）。

    拼接关系标注规则（用户要求：标注在「主/宿主(host)」段上，供给段不标）：
    - 宿主-供给类(host_provider/mixed_donor/hub_graph)：宿主段(host, 带 spliced_from)标注
      {length}（+{spliced_from}={original_length}）；供给段(provider)只标本段实长。
    - 链式续接类(无 provider 配对，捐赠方为上一根余料非绘制段)：仍标注在接收段(spliced_from)上。
    """
    length = tube['tube_length']
    nominal = _nominal_tube_length(tube)

    # 供给段(provider)：不标注拼接关系，仅保留孤岛原长说明
    if tube.get('host_role') == 'provider':
        if tube.get('orphan_trim_mm') and length != nominal:
            return f"{length}（原长{nominal}）"
        return str(length)

    # 宿主段(host, 带 spliced_from)：标注拼接关系 {length}（+{spliced_from}={orig}）
    if 'spliced_from' in tube and tube.get('host_role') == 'host':
        orig = tube.get('original_length', nominal)
        if use_full_splice_label:
            dim_text = f"{length}（+{tube['spliced_from']}={orig}"
            if tube.get('orphan_trim_mm'):
                dim_text += f"，原长{nominal}"
            return dim_text + "）"
        if tube.get('orphan_trim_mm') and length != nominal:
            return f"{length}（原长{nominal}）"
        return str(length)

    # 链式续接接收段(无 host_role)：维持原标注（捐赠方为上一根余料，非绘制段）
    if 'spliced_from' in tube and tube.get('host_role') not in ('provider', 'host'):
        orig = tube.get('original_length', nominal)
        show_full = use_full_splice_label
        if not show_full and first_sp_j is not None and segment_index == first_sp_j and tube.get('orphan_trim_mm'):
            show_full = True
        if show_full:
            dim_text = f"{length}（+{tube['spliced_from']}={orig}"
            if tube.get('orphan_trim_mm'):
                dim_text += f"，原长{nominal}"
            return dim_text + "）"
        if tube.get('orphan_trim_mm'):
            return f"{length}（原长{nominal}）"

    if tube.get('orphan_trim_mm') and length != nominal:
        return f"{length}（原长{nominal}）"
    return str(length)


def _split_orphan_leftover_hundreds(leftover_r, nominal_l):
    """
    将无法直接拼接的孤岛余料拆为 (废料段, 续接段)，两段均为整百 mm。
    续接段 carry 与下一根实切 partner 拼成一根 nominal_l，且 partner > SPLICE_THRESHOLD。
    例：3800 + 4100 产品 → 3400 续接 + 400 废料（700 实切拼接）。
    """
    if not ENABLE_ORPHAN_HUNDRED_SPLIT_REPAIR:
        return None
    if leftover_r <= SPLICE_THRESHOLD or nominal_l <= leftover_r:
        return None
    if nominal_l - leftover_r > SPLICE_THRESHOLD:
        return None
    for carry in range((leftover_r // 100) * 100, 0, -100):
        waste = leftover_r - carry
        if waste <= 0 or waste % 100 != 0:
            continue
        if nominal_l - carry <= SPLICE_THRESHOLD:
            continue
        return waste, carry
    return None


def _guess_dominant_tube_length(remaining_tubes):
    if not remaining_tubes:
        return None
    from collections import Counter
    return Counter(t['tube_length'] for t in remaining_tubes).most_common(1)[0][0]


def _commit_plan_leftover_to_queue(final_leftover, leftovers, remaining_tubes, plan_id, splice_info):
    """
    将本根尾余料写入拼接队列。
    若库存方管无法直接承接（partner<=阈值，即孤岛余料），在排料阶段整百拆成
    废料(记入本根 remaining_length) + 续接段(入 leftovers，供下一根 _consume_pending_leftovers 消费并 pop 方管)。
    """
    if final_leftover <= SPLICE_THRESHOLD:
        return final_leftover, leftovers

    if _can_splice_leftover_with_pool(final_leftover, remaining_tubes):
        leftovers.append(final_leftover)
        splice_info['length'] = final_leftover
        splice_info['to_plan'] = plan_id + 1
        return final_leftover, leftovers

    nominal = _guess_dominant_tube_length(remaining_tubes)
    if nominal:
        split = _split_orphan_leftover_hundreds(final_leftover, nominal)
        if split:
            waste, carry = split
            leftovers.append(carry)
            splice_info['length'] = carry
            splice_info['to_plan'] = plan_id + 1
            return waste, leftovers

    leftovers.append(final_leftover)
    splice_info['length'] = final_leftover
    splice_info['to_plan'] = plan_id + 1
    return final_leftover, leftovers


def _link_orphan_to_consumer(orphan_plan, consumer, orphan_pid, carry_len, partner_len, nominal_l):
    """写入孤岛方案与消费方之间的拼接关联。"""
    splice_info = orphan_plan.setdefault(
        'splice_info', {'from_plan': None, 'to_plan': None, 'length': 0}
    )
    splice_info['to_plan'] = consumer.get('plan_id')
    splice_info['length'] = carry_len
    consumer_info = consumer.setdefault(
        'splice_info', {'from_plan': None, 'to_plan': None, 'length': 0}
    )
    if consumer_info.get('from_plan') is None:
        consumer_info['from_plan'] = orphan_pid


def count_delivered_products(plans):
    """已交付产品根数（与输入库存 quantity 对齐，每切段对应一根库存方管）。"""
    total = 0
    for plan in plans:
        rm = plan.get('raw_materials', 1)
        for _tube in plan.get('tubes', []):
            if _tube.get('host_role') == 'provider':
                continue
            total += rm
    return total


def _transform_ref_tube_to_splice(ref_tube, carry_len, nominal_l):
    """将已 pop 的首段方管就地改为续接实切段（不新增切段、不重复扣库存）。"""
    partner = nominal_l - carry_len
    ref_tube['tube_length'] = partner
    ref_tube['spliced_from'] = carry_len
    ref_tube['original_length'] = nominal_l
    ref_tube['nominal_tube_length'] = nominal_l


def _prepend_carry_splice_tube(consumer, carry_len, nominal_l, ref_tube):
    """孤岛后处理：首段方管就地改为续接实切（与排料阶段 _consume_pending_leftovers 口径一致）。"""
    _transform_ref_tube_to_splice(ref_tube, carry_len, nominal_l)
    consumer['pieces'] = len(consumer.get('tubes', []))


def _try_orphan_direct_prepend_repair(orphan_plan, consumer, orphan_pid, leftover_r, raw_length):
    """余料与下一根原长差值已大于阈值时，在消费方首段前插入实切拼接段（整段余料续接）。"""
    if any('spliced_from' in t for t in consumer.get('tubes', [])):
        return False
    ref_tube = next(
        (t for t in consumer.get('tubes', [])
         if 'spliced_from' not in t and t.get('host_role') not in ('provider', 'host')),
        None,
    )
    if ref_tube is None:
        return False
    nominal_l = _nominal_tube_length(ref_tube)
    partner = nominal_l - leftover_r
    if partner <= SPLICE_THRESHOLD:
        return False
    _prepend_carry_splice_tube(consumer, leftover_r, nominal_l, ref_tube)
    _link_orphan_to_consumer(orphan_plan, consumer, orphan_pid, leftover_r, partner, nominal_l)
    orphan_plan['remaining_length'] = 0
    _refresh_plan_remaining(consumer, raw_length)
    logging.info(
        "孤岛余料拼接：方案#%s 余料 %s -> 方案#%s 方管原长 %s 实切 %s",
        orphan_pid, leftover_r, consumer.get('plan_id'), nominal_l, partner,
    )
    return True


def _try_orphan_hundred_split_repair(orphan_plan, consumer, orphan_pid, leftover_r, raw_length):
    """整百拆分续接：余料拆成废料 + 续接段，下一根首段实切拼接。"""
    if any('spliced_from' in t for t in consumer.get('tubes', [])):
        return False
    ref_tube = next(
        (t for t in consumer.get('tubes', [])
         if 'spliced_from' not in t and t.get('host_role') not in ('provider', 'host')),
        None,
    )
    if ref_tube is None:
        return False
    nominal_l = _nominal_tube_length(ref_tube)
    split = _split_orphan_leftover_hundreds(leftover_r, nominal_l)
    if not split:
        return False
    waste, carry = split
    partner = nominal_l - carry
    _prepend_carry_splice_tube(consumer, carry, nominal_l, ref_tube)
    _link_orphan_to_consumer(orphan_plan, consumer, orphan_pid, carry, partner, nominal_l)
    orphan_plan['remaining_length'] = waste
    _refresh_plan_remaining(consumer, raw_length)
    logging.info(
        "孤岛整百拆分：方案#%s 余料 %s -> 废料 %s + 续接 %s -> 方案#%s 首段实切 %s（拼成 %s）",
        orphan_pid, leftover_r, waste, carry, consumer.get('plan_id'), partner, nominal_l,
    )
    return True


def repair_orphan_islands_by_trim(plans, raw_length, trim_mm=None):
    """
    消除「孤岛余料」：
    1) 后续原材上少切 trim_mm 直接拼接；
    2) 仍无法拼接时，整百拆成「续接段 + 废料」，下一根首段实切承接（可链式重复）。
    """
    trim_mm = ORPHAN_TRIM_MM if trim_mm is None else trim_mm
    if not ENABLE_ORPHAN_TRIM_REPAIR and not ENABLE_ORPHAN_HUNDRED_SPLIT_REPAIR:
        return plans
    if not plans:
        return plans

    plans = copy.deepcopy(plans)
    plan_by_id = {p.get('plan_id'): p for p in plans}
    max_rounds = max(len(plans) * 2, 1)

    for _ in range(max_rounds):
        is_valid, violations = validate_strict_constraint(plans, raw_length)
        if is_valid:
            break
        orphan_violations = [v for v in violations if v[2] and '孤岛' in v[2]]
        if not orphan_violations:
            break

        fixed = False
        for orphan_pid, leftover_r, _ in orphan_violations:
            orphan_plan = plan_by_id.get(orphan_pid)
            if orphan_plan is None:
                continue
            width = orphan_plan.get('tube_width')
            group = sorted(
                [p for p in plans if p.get('tube_width') == width],
                key=lambda x: x.get('plan_id', 0),
            )
            if not group or group[-1].get('plan_id') == orphan_pid:
                continue

            last_plan_id = group[-1].get('plan_id')
            # 优先由紧邻的下一根原材承接（形成 #16→#17→#18 链式续接，而非跳到末根）
            candidates = [p for p in group if p.get('plan_id', 0) > orphan_pid]
            for consumer in candidates:
                is_last_bar = consumer.get('plan_id') == last_plan_id
                effective_trim = 0 if is_last_bar else trim_mm
                if _try_orphan_direct_prepend_repair(
                    orphan_plan, consumer, orphan_pid, leftover_r, raw_length
                ):
                    fixed = True
                    break
                if ENABLE_ORPHAN_HUNDRED_SPLIT_REPAIR and _try_orphan_hundred_split_repair(
                    orphan_plan, consumer, orphan_pid, leftover_r, raw_length
                ):
                    fixed = True
                    break
                if ENABLE_ORPHAN_TRIM_REPAIR and trim_mm > 0:
                    for tube in consumer.get('tubes', []):
                        if 'spliced_from' in tube or tube.get('host_role') in ('provider', 'host'):
                            continue
                        nominal_l = _nominal_tube_length(tube)
                        new_seg = nominal_l - leftover_r - effective_trim
                        if new_seg <= SPLICE_THRESHOLD:
                            continue
                        if nominal_l - leftover_r <= SPLICE_THRESHOLD:
                            continue

                        tube['spliced_from'] = leftover_r
                        tube['tube_length'] = new_seg
                        tube['nominal_tube_length'] = nominal_l
                        tube['original_length'] = nominal_l
                        if effective_trim > 0:
                            tube['orphan_trim_mm'] = effective_trim

                        _link_orphan_to_consumer(
                            orphan_plan, consumer, orphan_pid, leftover_r, new_seg, nominal_l)

                        _refresh_plan_remaining(consumer, raw_length)
                        if effective_trim > 0:
                            logging.info(
                                "孤岛减短修复：方案#%s 余料 %s -> 方案#%s 方管原长 %s 实切 %s（末根外再减 %s）",
                                orphan_pid, leftover_r, consumer.get('plan_id'),
                                nominal_l, new_seg, effective_trim,
                            )
                        else:
                            logging.info(
                                "孤岛余料拼接：方案#%s 余料 %s -> 方案#%s 方管原长 %s 实切 %s",
                                orphan_pid, leftover_r, consumer.get('plan_id'),
                                nominal_l, new_seg,
                            )
                        fixed = True
                        break
                if fixed:
                    break
            if fixed:
                break
        if not fixed:
            break

    return plans


# 模拟messagebox模块，以确保csv_to_dxf在命令行环境中正常工作
try:
    import tkinter.messagebox as messagebox
except ImportError:
    # 在命令行环境中，创建一个模拟的messagebox模块
    class MockMessageBox:
        @staticmethod
        def showwarning(title, message):
            print(f"WARNING: {title}: {message}")
    messagebox = MockMessageBox()

# 添加当前目录到Python路径，确保能找到csv_to_dxf模块
sys.path.insert(0, os.path.dirname(__file__))

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入日志模块
from app.utils.logger import function_logger as logging
from app.utils.logger import function_alarm_logger as alarm_logging

from csv_to_dxf import csv_to_dxf


@dataclass
class AlgorithmStage:
    """串联算法阶段配置。"""
    name: str
    max_plans: Optional[int] = None


class CuttingAlgorithmBase:
    """切割算法基类，后续新算法继承此类并实现 generate。"""

    name = "base"

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        raise NotImplementedError


class LegacyGreedyAlgorithm(CuttingAlgorithmBase):
    """当前版本默认算法：贪心+组合尝试+拼接。"""

    name = "legacy_greedy"

    def __init__(self, deep_first=False, presearch_first=False):
        self.deep_first = deep_first
        self.presearch_first = presearch_first
        self.last_run_stats = {
            "normal_perfect_raw_materials": 0,
            "deep_perfect_raw_materials": 0,
            "perfect_no_splice_raw_materials": 0
        }
        self._preferred_length_combos = set()

    def _apply_greedy_fill(self, remaining_tubes, leftovers, current_raw, remaining_length):
        carry, leftovers = _consume_pending_leftovers(remaining_tubes, leftovers)
        for seg in carry:
            current_raw.append(seg)
            remaining_length -= seg['tube_length']
        if not carry and leftovers:
            leftovers = []

        initial_pack_budget = remaining_length
        # 有界背包（二进制拆分）替代指数级子集 DFS：与原逻辑同为全局最优 pack key，量级 O(W × bundles)。
        # 质量并列时偏好已出现过的长度组合，提高 DXF 合并率。
        # 注意：不对「同长度不同型号」做强制对齐——型号必须一致才能合并，强行对齐会拆散本可合并的链。
        indices_to_pop, used_sum = _bounded_knapsack_pack_indices(
            remaining_tubes, remaining_length, self._preferred_length_combos
        )

        if indices_to_pop and used_sum > 0 and used_sum <= initial_pack_budget:
            for idx in indices_to_pop:
                tube = remaining_tubes[idx]
                current_raw.append(tube)
                remaining_length -= tube['tube_length']
                remaining_tubes.pop(idx)
        else:
            i = 0
            while i < len(remaining_tubes) and remaining_length > SPLICE_THRESHOLD:
                tube = remaining_tubes[i]
                if tube['tube_length'] <= remaining_length:
                    current_raw.append(tube)
                    remaining_length -= tube['tube_length']
                    remaining_tubes.pop(i)
                else:
                    i += 1

            i = len(remaining_tubes) - 1
            while i >= 0 and remaining_length > SPLICE_THRESHOLD:
                tube = remaining_tubes[i]
                if tube['tube_length'] <= remaining_length:
                    current_raw.append(tube)
                    remaining_length -= tube['tube_length']
                    remaining_tubes.pop(i)
                i -= 1

        return current_raw, remaining_length, leftovers

    def _take_same_length_perfect_cut(self, remaining_tubes, raw_length):
        """
        第一阶段：同长度完美切割（余料 <= SPLICE_THRESHOLD）。
        """
        current_raw = []
        length_counts = {}
        for tube in remaining_tubes:
            length = tube['tube_length']
            length_counts[length] = length_counts.get(length, 0) + 1

        best_choice = None  # (leftover, tube_length, num_tubes)
        for tube_length, count in length_counts.items():
            max_num_tubes = min(count, raw_length // tube_length)
            if max_num_tubes <= 0:
                continue
            for num_tubes in range(max_num_tubes, 0, -1):
                used_length = num_tubes * tube_length
                leftover = raw_length - used_length
                if 0 <= leftover <= SPLICE_THRESHOLD:
                    candidate = (leftover, tube_length, num_tubes)
                    if best_choice is None or candidate < best_choice:
                        best_choice = candidate
                    break

        if best_choice is None:
            return current_raw, False, raw_length

        _, tube_length, target_num = best_choice
        taken = 0
        i = 0
        while taken < target_num and i < len(remaining_tubes):
            if remaining_tubes[i]['tube_length'] == tube_length:
                current_raw.append(remaining_tubes.pop(i))
                taken += 1
            else:
                i += 1

        used = sum(t['tube_length'] for t in current_raw)
        return current_raw, True, raw_length - used

    def _find_four_segment_perfect_indices(self, remaining_tubes, raw_length):
        """
        第二阶段深度搜索：在全部剩余方管中搜索 4 段完美切割
        （4 段和使余料 <= SPLICE_THRESHOLD，且尽量接近 raw_length）。
        """
        n = len(remaining_tubes)
        if n < 4:
            return None

        # 使用长度对索引进行排序，可在 DFS 中做剪枝，减少搜索规模
        sorted_indices = sorted(range(n), key=lambda idx: remaining_tubes[idx]['tube_length'])
        sorted_lengths = [remaining_tubes[idx]['tube_length'] for idx in sorted_indices]

        best_result = None
        best_leftover = None

        def dfs(start_pos, depth, current_sum, picked_positions):
            nonlocal best_result, best_leftover
            if depth == 4:
                if current_sum <= raw_length:
                    leftover = raw_length - current_sum
                    if leftover <= SPLICE_THRESHOLD:
                        if best_leftover is None or leftover < best_leftover:
                            best_leftover = leftover
                            best_result = [sorted_indices[pos] for pos in picked_positions]
                return
            if current_sum >= raw_length:
                return

            remaining_slots = 4 - depth
            if start_pos + remaining_slots > n:
                return

            # 下界/上界剪枝
            min_possible = current_sum + sum(sorted_lengths[start_pos:start_pos + remaining_slots])
            if min_possible > raw_length:
                return
            max_possible = current_sum + sum(sorted_lengths[n - remaining_slots:n])
            if max_possible < raw_length - SPLICE_THRESHOLD:
                return

            for pos in range(start_pos, n):
                length = sorted_lengths[pos]
                next_sum = current_sum + length
                if next_sum > raw_length:
                    # 升序数组，后续只会更大
                    break
                picked_positions.append(pos)
                dfs(pos + 1, depth + 1, next_sum, picked_positions)
                picked_positions.pop()
                if best_leftover == 0:
                    # 已经是最优余料，直接停止
                    return

        dfs(0, 0, 0, [])
        return best_result

    def _take_four_segment_perfect_cut(self, remaining_tubes, raw_length):
        current_raw = []
        matched_indices = self._find_four_segment_perfect_indices(remaining_tubes, raw_length)
        if not matched_indices:
            return current_raw, False, raw_length

        # 按索引倒序弹出，避免索引偏移
        for idx in sorted(matched_indices, reverse=True):
            current_raw.append(remaining_tubes.pop(idx))
        # 还原为原顺序（便于后续绘图一致性）
        current_raw.reverse()
        used = sum(t['tube_length'] for t in current_raw)
        return current_raw, True, raw_length - used

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        cutting_plans = []
        plan_id = start_plan_id
        generated_count = 0
        leftovers = leftovers if leftovers is not None else []
        self._preferred_length_combos = set()

        while remaining_tubes and (max_plans is None or generated_count < max_plans):
            current_raw = []
            remaining_length = raw_length
            perfect_source = None
            deep_search_used = False

            if self.presearch_first:
                # 并联方案0：先普通搜索+深度搜索，再贪心（历史方案）
                normal_raw, normal_found, normal_leftover = self._take_same_length_perfect_cut(
                    remaining_tubes,
                    remaining_length
                )
                if normal_found:
                    current_raw.extend(normal_raw)
                    remaining_length = normal_leftover
                    perfect_source = "normal"
                else:
                    deep_raw, deep_found, deep_leftover = self._take_four_segment_perfect_cut(
                        remaining_tubes,
                        remaining_length
                    )
                    if deep_found:
                        current_raw.extend(deep_raw)
                        remaining_length = deep_leftover
                        deep_search_used = True
                        perfect_source = "deep"

                current_raw, remaining_length, leftovers = self._apply_greedy_fill(
                    remaining_tubes, leftovers, current_raw, remaining_length
                )
            elif self.deep_first:
                # 并联方案2：先深搜，再贪心
                if remaining_tubes and remaining_length > SPLICE_THRESHOLD:
                    deep_raw, deep_found, deep_leftover = self._take_four_segment_perfect_cut(
                        remaining_tubes,
                        remaining_length
                    )
                    if deep_found:
                        current_raw.extend(deep_raw)
                        remaining_length = deep_leftover
                        deep_search_used = True
                current_raw, remaining_length, leftovers = self._apply_greedy_fill(
                    remaining_tubes, leftovers, current_raw, remaining_length
                )
            else:
                # 并联方案1：先贪心，再深搜
                current_raw, remaining_length, leftovers = self._apply_greedy_fill(
                    remaining_tubes, leftovers, current_raw, remaining_length
                )
                if remaining_tubes and remaining_length > SPLICE_THRESHOLD:
                    deep_raw, deep_found, deep_leftover = self._take_four_segment_perfect_cut(
                        remaining_tubes,
                        remaining_length
                    )
                    if deep_found:
                        current_raw.extend(deep_raw)
                        remaining_length = deep_leftover
                        deep_search_used = True

            if current_raw:
                final_leftover = remaining_length
                splice_info = {
                    'from_plan': None,
                    'to_plan': None,
                    'length': 0
                }
                final_leftover, leftovers = _commit_plan_leftover_to_queue(
                    final_leftover, leftovers, remaining_tubes, plan_id, splice_info,
                )
                if final_leftover > SPLICE_THRESHOLD:
                    splice_info['from_plan'] = plan_id
                    if splice_info.get('length', 0) == 0:
                        splice_info['length'] = final_leftover

                has_splice_seg = any('spliced_from' in t for t in current_raw)
                cutting_plan = {
                    'plan_id': plan_id,
                    'tube_width': current_raw[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': current_raw,
                    'pieces': len(current_raw),
                    'raw_materials': 1,
                    'splice': final_leftover > SPLICE_THRESHOLD or has_splice_seg or bool(splice_info.get('to_plan')),
                    'splice_info': splice_info,
                    'perfect_source': perfect_source
                }
                if final_leftover <= SPLICE_THRESHOLD and not has_splice_seg:
                    cutting_plan['perfect_source'] = "deep" if deep_search_used else "normal"
                cutting_plans.append(cutting_plan)
                combo_key = _plan_solid_length_combo(cutting_plan)
                if combo_key:
                    self._preferred_length_combos.add(combo_key)

                plan_id += 1
                generated_count += 1
            else:
                # 防止死循环：当前算法无法继续构造新方案时退出
                break

        # 统计口径：无拼接完美切割（余料 <= 阈值，且无 spliced_from / 无宿主段）
        def is_no_splice_perfect(plan):
            return is_no_splice_perfect_cut(plan, raw_length)

        normal_perfect_raw_materials = sum(
            p.get('raw_materials', 1) for p in cutting_plans
            if is_no_splice_perfect(p) and p.get('perfect_source') == "normal"
        )
        deep_perfect_raw_materials = sum(
            p.get('raw_materials', 1) for p in cutting_plans
            if is_no_splice_perfect(p) and p.get('perfect_source') == "deep"
        )

        perfect_no_splice_raw_materials = sum(
            p.get('raw_materials', 1)
            for p in cutting_plans
            if is_no_splice_perfect(p)
        )

        self.last_run_stats = {
            "normal_perfect_raw_materials": normal_perfect_raw_materials,
            "deep_perfect_raw_materials": deep_perfect_raw_materials,
            "perfect_no_splice_raw_materials": perfect_no_splice_raw_materials
        }
        logging.info(
            "完美切割原材统计 - 普通搜索: %s, 深度搜索: %s, 无拼接完美切割合计: %s",
            normal_perfect_raw_materials,
            deep_perfect_raw_materials,
            perfect_no_splice_raw_materials
        )

        return cutting_plans, remaining_tubes, leftovers, plan_id


class GreedyThenDeepAlgorithm(LegacyGreedyAlgorithm):
    name = "greedy_then_deep"

    def __init__(self):
        super().__init__(deep_first=False)


class DeepThenGreedyAlgorithm(LegacyGreedyAlgorithm):
    name = "deep_then_greedy"

    def __init__(self):
        super().__init__(deep_first=True)


class NormalDeepThenGreedyAlgorithm(LegacyGreedyAlgorithm):
    name = "normal_deep_then_greedy"

    def __init__(self):
        super().__init__(deep_first=False, presearch_first=True)


class UniformFourBarChainAlgorithm(CuttingAlgorithmBase):
    """
    单规格方管的四段拼接链（人工常用排法）：
      原材1: 4×L + 尾料 R0
      原材2: (L-R0)+R0拼 + 3×L + 尾料 R1
      原材3: (L-R1)+R1拼 + 3×L + (L-R0) + R0拼 + 尾料 R2
      原材4: 4×L + 尾料 R0  → 下一周期原材2 消费 R0
    其中 R0 = raw_length - 4L（如 12000/2800 → 800），每 4 根原材消耗 16 根成品方管。
    """

    name = "uniform_four_bar_chain"

    TUBES_PER_FULL_CYCLE = 17  # 原材 A/B/D 各 4 根 + 原材 C 5 根
    TAIL_TUBE_COUNT = 9       # 收尾 3 根原材（4+4+1 根方管），如 128=7×17+9 → 31 根原材

    @staticmethod
    def _cycle_layout(tube_count):
        """返回 (完整四段周期数, 收尾方管数) 或 None。"""
        n = tube_count
        if n < UniformFourBarChainAlgorithm.TUBES_PER_FULL_CYCLE:
            return None
        if n % UniformFourBarChainAlgorithm.TUBES_PER_FULL_CYCLE == 0:
            return n // UniformFourBarChainAlgorithm.TUBES_PER_FULL_CYCLE, 0
        tail = UniformFourBarChainAlgorithm.TAIL_TUBE_COUNT
        if n >= tail and (n - tail) % UniformFourBarChainAlgorithm.TUBES_PER_FULL_CYCLE == 0:
            return (n - tail) // UniformFourBarChainAlgorithm.TUBES_PER_FULL_CYCLE, tail
        return None

    @staticmethod
    def _can_apply(remaining_tubes, raw_length):
        if not remaining_tubes:
            return False
        lengths = {t['tube_length'] for t in remaining_tubes}
        if len(lengths) != 1:
            return False
        L = next(iter(lengths))
        tail = raw_length - 4 * L
        if tail <= SPLICE_THRESHOLD or tail >= L:
            return False
        partner = L - tail
        mid_tail = raw_length - partner - 3 * L
        row3_tail = raw_length - (L - mid_tail) - 3 * L - partner
        if row3_tail < 0 or row3_tail > SPLICE_THRESHOLD:
            return False
        if mid_tail <= SPLICE_THRESHOLD or mid_tail >= L:
            return False
        return UniformFourBarChainAlgorithm._cycle_layout(len(remaining_tubes)) is not None

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        leftovers = leftovers if leftovers is not None else []
        if leftovers:
            return [], remaining_tubes, leftovers, start_plan_id
        if not self._can_apply(remaining_tubes, raw_length):
            return [], remaining_tubes, leftovers, start_plan_id

        L = remaining_tubes[0]['tube_length']
        tail = raw_length - 4 * L
        partner = L - tail
        mid_tail = raw_length - partner - 3 * L
        row3_tail = raw_length - (L - mid_tail) - 3 * L - partner
        layout = self._cycle_layout(len(remaining_tubes))
        n_cycles, tail_tubes = layout

        plans = []
        plan_id = start_plan_id
        idx = 0

        def take_tube():
            nonlocal idx
            t = copy.deepcopy(remaining_tubes[idx])
            idx += 1
            return t

        def take_full(n):
            return [take_tube() for _ in range(n)]

        def make_splice_tube(base, cut_len, spliced_from, nominal=None):
            t = copy.deepcopy(base)
            nom = nominal or L
            t['tube_length'] = cut_len
            t['spliced_from'] = spliced_from
            t['original_length'] = nom
            t['nominal_tube_length'] = nom
            return t

        def append_plan(tubes, rem, to_plan=None, from_plan=None, link_len=0):
            nonlocal plan_id
            plan = {
                'plan_id': plan_id,
                'tube_width': tubes[0].get('tube_width', 0),
                'raw_length': raw_length,
                'remaining_length': rem,
                'tubes': tubes,
                'pieces': len(tubes),
                'raw_materials': 1,
                'splice': rem > SPLICE_THRESHOLD or any('spliced_from' in t for t in tubes),
                'splice_info': {
                    'from_plan': from_plan,
                    'to_plan': to_plan,
                    'length': link_len if link_len > SPLICE_THRESHOLD else 0,
                },
                'perfect_source': 'uniform_chain',
            }
            plans.append(plan)
            plan_id += 1

        for _ in range(n_cycles):
            # 原材 A：4×L，尾 R0
            bar1 = take_full(4)
            append_plan(bar1, tail, to_plan=plan_id + 1, from_plan=plan_id, link_len=tail)

            # 原材 B：R0 拼 + 3×L，尾 R1
            bar2 = [make_splice_tube(take_tube(), partner, tail)] + take_full(3)
            append_plan(bar2, mid_tail, to_plan=plan_id + 1, from_plan=plan_id, link_len=mid_tail)

            # 原材 C：R1 拼 + 3×L + (L-R0) 拼（末段与下一根 D 的 R0 拼成一根 L）
            bar3 = take_full(5)
            bar3[0] = make_splice_tube(bar3[0], L - mid_tail, mid_tail)
            bar3[4] = make_splice_tube(bar3[4], partner, tail)
            append_plan(bar3, row3_tail, to_plan=plan_id + 1, from_plan=plan_id, link_len=row3_tail)

            # 原材 D：4×L，尾 R0 → 下一周期原材 B（跳过下一周期的原材 A）
            bar4 = take_full(4)
            next_to = plan_id + 2 if idx < len(remaining_tubes) else None
            append_plan(bar4, tail, to_plan=next_to, from_plan=plan_id, link_len=tail)

        if tail_tubes == self.TAIL_TUBE_COUNT:
            # 收尾：原材 A + 原材 B + 原材 C 仅消费 1 根（余下长料可跨项目复用）
            bar1 = take_full(4)
            append_plan(bar1, tail, to_plan=plan_id + 1, from_plan=plan_id, link_len=tail)
            bar2 = [make_splice_tube(take_tube(), partner, tail)] + take_full(3)
            append_plan(bar2, mid_tail, to_plan=plan_id + 1, from_plan=plan_id, link_len=mid_tail)
            bar3 = [make_splice_tube(take_tube(), L - mid_tail, mid_tail)]
            append_plan(bar3, raw_length - (L - mid_tail), to_plan=None, from_plan=plan_id, link_len=0)

        logging.info(
            "单规格四段链：L=%s, 完整周期=%s, 收尾方管=%s, 原材=%s, 拼接段=%s",
            L, n_cycles, tail_tubes, len(plans),
            sum(1 for p in plans for t in p['tubes'] if 'spliced_from' in t),
        )
        return plans, [], leftovers, plan_id


class HostProviderAlgorithm(CuttingAlgorithmBase):
    """
    宿主-供给模式算法：
    - 同一型号 L 的多根需求时，生成宿主原材按 K 整管 + R 待拼接段 模板切割
    - 单独使用一根供给原材，切出 P=L-R 的若干段去配齐宿主中的待拼接段
    - 供给原材剩余 -> 进入余料池供后续切割使用
    要求：R > SPLICE_THRESHOLD 且 P = L - R > SPLICE_THRESHOLD
    """

    name = "host_provider"

    def __init__(self):
        self.last_run_stats = {
            "host_raw_count": 0,
            "provider_raw_count": 0,
            "perfect_no_splice_raw_materials": 0
        }

    def _select_dominant_length(self, remaining_tubes):
        """选择当前最适合作为宿主模板的产品长度（数量最多者）。"""
        counts = {}
        for tube in remaining_tubes:
            counts[tube['tube_length']] = counts.get(tube['tube_length'], 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _try_use_leftover_segment(self, remaining_tubes, segment_length, plan_id, raw_length):
        """
        尝试用一段单独“整块剩余”切割普通方管（不引入拼接）。
        将切出的方管返回为一个普通切割方案，segment 末尾废料并入返回信息。
        """
        if segment_length <= 0 or not remaining_tubes:
            return None, remaining_tubes
        candidate_lengths = sorted({t['tube_length'] for t in remaining_tubes}, reverse=True)
        used_tubes = []
        used_length = 0
        for L in candidate_lengths:
            while used_length + L <= segment_length:
                # 找一根该长度的方管
                idx = next((i for i, t in enumerate(remaining_tubes) if t['tube_length'] == L), None)
                if idx is None:
                    break
                used_tubes.append(remaining_tubes.pop(idx))
                used_length += L
        if not used_tubes:
            return None, remaining_tubes
        leftover = segment_length - used_length
        plan = {
            'plan_id': plan_id,
            'tube_width': used_tubes[0]['tube_width'],
            'raw_length': raw_length,
            'remaining_length': leftover,
            'tubes': used_tubes,
            'pieces': len(used_tubes),
            'raw_materials': 1,
            'splice': False,
            'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
            'perfect_source': "host_provider_reuse" if leftover <= SPLICE_THRESHOLD else None
        }
        return plan, remaining_tubes

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        cutting_plans = []
        plan_id = start_plan_id
        leftovers = leftovers if leftovers is not None else []
        host_count = 0
        provider_count = 0

        while remaining_tubes and (max_plans is None or len(cutting_plans) < max_plans):
            carry, leftovers = _consume_pending_leftovers(remaining_tubes, leftovers)
            if carry:
                used_len = sum(t['tube_length'] for t in carry)
                final_leftover = raw_length - used_len
                plan = {
                    'plan_id': plan_id,
                    'tube_width': carry[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': carry,
                    'pieces': len(carry),
                    'raw_materials': 1,
                    'splice': any('spliced_from' in t for t in carry),
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': None,
                }
                if final_leftover > SPLICE_THRESHOLD:
                    plan['splice_info']['to_plan'] = plan_id + 1
                    plan['splice_info']['length'] = final_leftover
                    leftovers.append(final_leftover)
                cutting_plans.append(plan)
                plan_id += 1
                continue

            L = self._select_dominant_length(remaining_tubes)
            if L is None or L <= 0 or L > raw_length:
                break

            # 计算宿主模板：K 整管 + R 待拼接段
            K = raw_length // L
            R = raw_length - K * L
            P = L - R if L > R else 0
            host_template_valid = (
                K > 0 and R > SPLICE_THRESHOLD and P > SPLICE_THRESHOLD
            )

            # 按 (长度, 型号) 分组：宿主必须同型号，避免改写/混淆产品型号。
            # 在主导长度内取数量最多的型号组作为本轮宿主对象。
            model_groups = {}
            for i, t in enumerate(remaining_tubes):
                if t['tube_length'] != L:
                    continue
                key = (t.get('yield_force'), t.get('product_length'))
                model_groups.setdefault(key, []).append(i)
            if not model_groups:
                break
            dominant_model_key = max(model_groups.items(), key=lambda kv: len(kv[1]))[0]
            same_length_indices = model_groups[dominant_model_key]
            same_length_count = len(same_length_indices)

            if not host_template_valid or same_length_count <= K:
                # 不足一组宿主(K+1)：切成普通原材消耗掉，不再 break 丢弃尾料。
                # 高于阈值的余料按新原则视为废料/可复用长料，由评分决定是否接受。
                if same_length_count <= 0:
                    break
                # 当前型号若数量 <= K，直接切一根原材就完事
                tubes_to_take = same_length_indices[:min(K, same_length_count)]
                if not tubes_to_take:
                    break
                used_tubes = []
                # 倒序弹出避免索引错位
                for idx in sorted(tubes_to_take, reverse=True):
                    used_tubes.append(remaining_tubes.pop(idx))
                used_tubes.reverse()
                used_length = sum(t['tube_length'] for t in used_tubes)
                final_leftover = raw_length - used_length
                plan = {
                    'plan_id': plan_id,
                    'tube_width': used_tubes[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': used_tubes,
                    'pieces': len(used_tubes),
                    'raw_materials': 1,
                    'splice': False,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': "normal" if final_leftover <= SPLICE_THRESHOLD else None
                }
                cutting_plans.append(plan)
                plan_id += 1
                if final_leftover > SPLICE_THRESHOLD:
                    leftovers.append(final_leftover)
                continue

            # 计算宿主数量：每根宿主提供 K + 1 根管（K 整管 + 1 拼接管）
            # 但宿主总根数受供给侧限制：单根供给原材最多切 X = raw_length // P 段
            X_per_provider = raw_length // P
            # 估算所需宿主数 M：先按数量上限尽量用满，余量留下后续轮处理
            # 1 根供给原材最多支撑 X_per_provider 个宿主
            M_max_by_provider = X_per_provider
            # 实际 M = min(剩余根数 / (K+1) 向下取整, M_max_by_provider)
            possible_hosts = same_length_count // (K + 1)
            M = min(possible_hosts, M_max_by_provider)
            if M <= 0:
                # 不足以做一组宿主-供给 -> 退化为切一根普通原材
                tubes_to_take = same_length_indices[:K]
                used_tubes = []
                for idx in sorted(tubes_to_take, reverse=True):
                    used_tubes.append(remaining_tubes.pop(idx))
                used_tubes.reverse()
                used_length = sum(t['tube_length'] for t in used_tubes)
                final_leftover = raw_length - used_length
                plan = {
                    'plan_id': plan_id,
                    'tube_width': used_tubes[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': used_tubes,
                    'pieces': len(used_tubes),
                    'raw_materials': 1,
                    'splice': False,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': "normal" if final_leftover <= SPLICE_THRESHOLD else None
                }
                cutting_plans.append(plan)
                plan_id += 1
                if final_leftover > SPLICE_THRESHOLD:
                    leftovers.append(final_leftover)
                continue

            # 取出本轮要消耗的方管：M*(K+1) 根
            need_tubes = M * (K + 1)
            taken = []
            for idx in same_length_indices[:need_tubes][::-1]:
                taken.append(remaining_tubes.pop(idx))
            taken.reverse()
            tube_width = taken[0]['tube_width']
            yield_force = taken[0]['yield_force']
            product_length = taken[0]['product_length']

            # 生成 M 个宿主原材：每个 = K 整管 + 1 拼接段(长度 R)
            host_plan_ids = []
            for i in range(M):
                host_tubes = []
                for j in range(K):
                    host_tubes.append({
                        'tube_length': L,
                        'product_length': product_length,
                        'yield_force': yield_force,
                        'tube_width': tube_width
                    })
                # 拼接段：以 spliced_from=P 表达“需另一段 P 来配齐为长度 L”
                host_tubes.append({
                    'tube_length': R,
                    'product_length': product_length,
                    'yield_force': yield_force,
                    'tube_width': tube_width,
                    'spliced_from': P,
                    'original_length': L,
                    'host_role': 'host'
                })
                host_plan = {
                    'plan_id': plan_id,
                    'tube_width': tube_width,
                    'raw_length': raw_length,
                    'remaining_length': 0,
                    'tubes': host_tubes,
                    'pieces': len(host_tubes),
                    'raw_materials': 1,
                    'splice': True,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': "host_provider_host"
                }
                cutting_plans.append(host_plan)
                host_plan_ids.append(plan_id)
                plan_id += 1
                host_count += 1

            # 生成 1 根供给原材：含 M 段长度 P 的拼接料
            provider_tubes = []
            for i in range(M):
                provider_tubes.append({
                    'tube_length': P,
                    'product_length': product_length,
                    'yield_force': yield_force,
                    'tube_width': tube_width,
                    'host_role': 'provider',
                    'pair_length': R,
                    'original_length': L
                })
            provider_used = M * P
            provider_leftover = raw_length - provider_used

            # 供给原材余量：背包优选填充（优先尾余<=阈值，避免贪心留下 1100 等可拼余料）
            if provider_leftover > 0 and remaining_tubes:
                extra_tubes, provider_leftover = _knapsack_pop_tubes_for_bar_fill(
                    remaining_tubes, provider_leftover
                )
                for t in extra_tubes:
                    provider_tubes.append({
                        'tube_length': t['tube_length'],
                        'product_length': t['product_length'],
                        'yield_force': t['yield_force'],
                        'tube_width': t['tube_width'],
                    })
                if extra_tubes and provider_leftover > SPLICE_THRESHOLD:
                    logging.info(
                        "供给原材背包填充：填入 %s 段，余料 %s（%s）",
                        len(extra_tubes),
                        provider_leftover,
                        "可拼下一根" if _can_splice_leftover_with_pool(
                            provider_leftover, remaining_tubes
                        ) else "待下一根处理",
                    )

            provider_plan = {
                'plan_id': plan_id,
                'tube_width': tube_width,
                'raw_length': raw_length,
                'remaining_length': provider_leftover,
                'tubes': provider_tubes,
                'pieces': len(provider_tubes),
                'raw_materials': 1,
                'splice': True,
                'splice_info': {
                    'from_plan': None, 'to_plan': None, 'length': 0,
                    'provider_for_hosts': list(host_plan_ids)
                },
                'perfect_source': "host_provider_provider"
            }
            cutting_plans.append(provider_plan)
            provider_plan_id = plan_id
            plan_id += 1
            provider_count += 1

            # 宿主-供给配对关系仅记录在 provider 侧（provider_for_hosts），
            # 不在宿主侧设 to_plan：宿主原材 remaining_length=0 无余料可消费，
            # 设 to_plan 反而把宿主并入拼接连通组，导致同型号宿主刀型无法在图面合并(×N)。
            # provider 侧若有余料续接下一根，仍按下方 to_plan 维持真实链关系。

            if provider_leftover > SPLICE_THRESHOLD:
                leftovers.append(provider_leftover)
                provider_plan['splice_info']['to_plan'] = plan_id
                provider_plan['splice_info']['length'] = provider_leftover

        # 统计无拼接完美切割（host-provider 自身的方案不算无拼接，但二次复用切的可能算）
        perfect_no_splice = sum(
            p.get('raw_materials', 1)
            for p in cutting_plans
            if is_no_splice_perfect_cut(p, raw_length)
        )
        self.last_run_stats = {
            "host_raw_count": host_count,
            "provider_raw_count": provider_count,
            "perfect_no_splice_raw_materials": perfect_no_splice
        }
        logging.info(
            "宿主-供给统计 - 宿主原材: %s, 供给原材: %s, 无拼接完美切割: %s",
            host_count, provider_count, perfect_no_splice
        )
        return cutting_plans, remaining_tubes, leftovers, plan_id


class MixedDonorHostProviderAlgorithm(CuttingAlgorithmBase):
    """
    混合捐赠-宿主算法（host_provider 变体）：
    与 host_provider 不同，供方不建「专用供管(全切成 P，0 成品)」，
    而是建「产品管 + 捐赠尾段」：每根供管先用产品把 raw-P 填满(背包)，
    再把 P 作为尾段捐赠给一个宿主的 R，拼成完整产品 L。
    适合产品能凑出 raw-P 的场景，避免专用供管浪费一根管的成品产能。
    剩余需求回退 GreedyThenDeep 处理。仅作并联候选，由评分决定是否选用。
    """

    name = "mixed_donor_host_provider"

    def _select_dominant_length(self, remaining_tubes):
        counts = {}
        for tube in remaining_tubes:
            counts[tube['tube_length']] = counts.get(tube['tube_length'], 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        cutting_plans = []
        plan_id = start_plan_id
        leftovers = leftovers if leftovers is not None else []
        host_count = 0
        donor_count = 0

        # 预留启发式：当存在两种非主导长度 G>S 且 G+2*S 接近 raw(完美管)时，
        # S 需要 G//2 配对做完美管，故捐赠尾管最多用掉 count_G - count_S//2 个 G，
        # 避免捐赠尾管把 G 全部吃光、导致 S 无法做完美管而多用料。
        def _max_donor_tubes(tubes, L_dom, raw_len):
            from collections import Counter
            cnt = Counter(t['tube_length'] for t in tubes)
            non_L = sorted([ln for ln in cnt if ln != L_dom], reverse=True)
            if len(non_L) < 2:
                return None  # 不限制
            G, S = non_L[0], non_L[1]
            if G + 2 * S <= raw_len and (raw_len - (G + 2 * S)) <= SPLICE_THRESHOLD:
                reserve_G = min(cnt[G], cnt[S] // 2)
                return max(0, cnt[G] - reserve_G)
            return None
        L_init = self._select_dominant_length(remaining_tubes)
        max_donor = _max_donor_tubes(remaining_tubes, L_init, raw_length) if L_init else None

        while remaining_tubes and (max_plans is None or len(cutting_plans) < max_plans):
            carry, leftovers = _consume_pending_leftovers(remaining_tubes, leftovers)
            if carry:
                used_len = sum(t['tube_length'] for t in carry)
                final_leftover = raw_length - used_len
                plan = {
                    'plan_id': plan_id,
                    'tube_width': carry[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': carry,
                    'pieces': len(carry),
                    'raw_materials': 1,
                    'splice': any('spliced_from' in t for t in carry),
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': None,
                }
                if final_leftover > SPLICE_THRESHOLD:
                    plan['splice_info']['to_plan'] = plan_id + 1
                    plan['splice_info']['length'] = final_leftover
                    leftovers.append(final_leftover)
                cutting_plans.append(plan)
                plan_id += 1
                continue

            L = self._select_dominant_length(remaining_tubes)
            if L is None or L <= 0 or L > raw_length:
                break

            K = raw_length // L
            R = raw_length - K * L
            P = L - R if L > R else 0
            host_template_valid = (
                K > 0 and R > SPLICE_THRESHOLD and P > SPLICE_THRESHOLD
            )

            # 按 (长度, 型号) 分组，宿主必须同型号
            model_groups = {}
            for i, t in enumerate(remaining_tubes):
                if t['tube_length'] != L:
                    continue
                key = (t.get('yield_force'), t.get('product_length'))
                model_groups.setdefault(key, []).append(i)
            if not model_groups:
                break
            dominant_model_key = max(model_groups.items(), key=lambda kv: len(kv[1]))[0]
            same_length_indices = model_groups[dominant_model_key]
            same_length_count = len(same_length_indices)

            if not host_template_valid or same_length_count < K + 1:
                # 不足一组宿主(K+1)：切普通原材消耗，不丢弃尾料
                if same_length_count <= 0:
                    break
                tubes_to_take = same_length_indices[:min(K, same_length_count)]
                if not tubes_to_take:
                    break
                used_tubes = []
                for idx in sorted(tubes_to_take, reverse=True):
                    used_tubes.append(remaining_tubes.pop(idx))
                used_tubes.reverse()
                used_length = sum(t['tube_length'] for t in used_tubes)
                final_leftover = raw_length - used_length
                plan = {
                    'plan_id': plan_id,
                    'tube_width': used_tubes[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': used_tubes,
                    'pieces': len(used_tubes),
                    'raw_materials': 1,
                    'splice': False,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': "normal" if final_leftover <= SPLICE_THRESHOLD else None
                }
                cutting_plans.append(plan)
                plan_id += 1
                if final_leftover > SPLICE_THRESHOLD:
                    leftovers.append(final_leftover)
                continue

            # 预留 K+1 根 L 管给宿主（先弹出）
            host_take = same_length_indices[:K + 1]
            reserved = []
            for idx in sorted(host_take, reverse=True):
                reserved.append(remaining_tubes.pop(idx))
            reserved.reverse()
            tube_width = reserved[0]['tube_width']
            yield_force = reserved[0]['yield_force']
            product_length = reserved[0]['product_length']

            # 建捐赠尾管：用剩余池填 raw-P（背包），要求填出产品且余料可接受
            packed, leftover_cap = _knapsack_pop_tubes_for_bar_fill(
                remaining_tubes, raw_length - P
            )
            donor_ok = bool(packed) and leftover_cap <= SPLICE_THRESHOLD
            # 预留上限：达到 max_donor 则停止混合捐赠，余量交回退算法(做完美管等)
            if donor_ok and max_donor is not None and donor_count >= max_donor:
                donor_ok = False
            if not donor_ok:
                # 放弃本轮混合捐赠：把预留 L 管放回，交回退算法处理
                if packed:
                    remaining_tubes.extend(packed)
                remaining_tubes.extend(reserved)
                break

            # 宿主管：K 整管 + R 拼接段
            host_tubes = []
            for j in range(K):
                host_tubes.append({
                    'tube_length': L,
                    'product_length': product_length,
                    'yield_force': yield_force,
                    'tube_width': tube_width
                })
            host_tubes.append({
                'tube_length': R,
                'product_length': product_length,
                'yield_force': yield_force,
                'tube_width': tube_width,
                'spliced_from': P,
                'original_length': L,
                'host_role': 'host'
            })
            host_plan = {
                'plan_id': plan_id,
                'tube_width': tube_width,
                'raw_length': raw_length,
                'remaining_length': 0,
                'tubes': host_tubes,
                'pieces': len(host_tubes),
                'raw_materials': 1,
                'splice': True,
                'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                'perfect_source': "host_provider_host"
            }
            cutting_plans.append(host_plan)
            host_plan_id = plan_id
            plan_id += 1
            host_count += 1

            # 捐赠尾管：packed 产品 + P 捐赠段
            donor_tubes = [dict(t) for t in packed]
            donor_tubes.append({
                'tube_length': P,
                'product_length': product_length,
                'yield_force': yield_force,
                'tube_width': tube_width,
                'host_role': 'provider',
                'pair_length': R,
                'original_length': L
            })
            donor_leftover = leftover_cap
            donor_plan = {
                'plan_id': plan_id,
                'tube_width': tube_width,
                'raw_length': raw_length,
                'remaining_length': donor_leftover,
                'tubes': donor_tubes,
                'pieces': len(donor_tubes),
                'raw_materials': 1,
                'splice': True,
                'splice_info': {
                    'from_plan': None, 'to_plan': None, 'length': 0,
                    'provider_for_hosts': [host_plan_id]
                },
                'perfect_source': "host_provider_provider"
            }
            cutting_plans.append(donor_plan)
            plan_id += 1
            donor_count += 1

            if donor_leftover > SPLICE_THRESHOLD:
                leftovers.append(donor_leftover)
                donor_plan['splice_info']['to_plan'] = plan_id
                donor_plan['splice_info']['length'] = donor_leftover

        # 剩余需求回退 StrictPhasedAlgorithm（含完美+链式+宿主，比纯贪心更优）
        if remaining_tubes:
            fb = StrictPhasedAlgorithm()
            extra, remain, _, _ = fb.generate(
                remaining_tubes=remaining_tubes,
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=leftovers,
                max_plans=max_plans
            )
            cutting_plans.extend(extra)
            remaining_tubes = remain

        logging.info(
            "混合捐赠-宿主统计 - 宿主原材: %s, 捐赠尾管: %s",
            host_count, donor_count
        )
        return cutting_plans, remaining_tubes, leftovers, plan_id


class UniformHubGraphAlgorithm(CuttingAlgorithmBase):
    """
    单规格枢纽图算法（daisy-chain/枢纽管的推广）：
    针对单一产品长度 L 的均匀需求，用「端管(provider, K整+rem捐赠段) + 枢纽管(host,
    (K-1)整+多个 (L-rem) 接收段)」构造拼接图，使拼接次数从 host_provider 的 N 次降到 s 次。
    推导: T=ceil(N*L/R), K=R//L, rem=R-K*L, D=N-T*K(整管缺口).
      端管捐赠 rem, 枢纽接收 L-rem, rem+(L-rem)=L. 每个拼接=1端+1枢纽.
      s 个端 + H=s-D 个枢纽 + P=T-s-H 个纯管. 枢纽容量 L+rem, 每枢纽最多 (L+rem)/(L-rem) 个接收段.
      最小 s = ceil( D*(L+rem)/(2*rem) ), 要求 600<rem<L-600 且 K>=2.
    所有段长 = rem 与 L-rem, 均 > SPLICE_THRESHOLD(600), 无需放宽阈值。
    非均匀长度或条件不满足时回退 StrictPhasedAlgorithm。仅作并联候选, 由评分决定是否选用。
    """

    name = "uniform_hub_graph"

    def _group_uniform(self, remaining_tubes):
        """按(长度,型号)分组, 返回 {key:[tubes]}; 仅当全局只有一种长度时可用。"""
        lengths = {t['tube_length'] for t in remaining_tubes}
        if len(lengths) != 1:
            return None, None
        L = next(iter(lengths))
        groups = {}
        for t in remaining_tubes:
            key = (t.get('yield_force'), t.get('product_length'))
            groups.setdefault(key, []).append(t)
        return L, groups

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        cutting_plans = []
        plan_id = start_plan_id
        leftovers = leftovers if leftovers is not None else []

        L, groups = self._group_uniform(remaining_tubes)
        # 条件: 单一长度, 且至少有一个型号组足够大可构造
        ok = False
        if L is not None and groups and L < raw_length:
            K = raw_length // L
            rem = raw_length - K * L
            # 段长合法性: rem 与 L-rem 都 > 阈值
            if K >= 2 and rem > SPLICE_THRESHOLD and (L - rem) > SPLICE_THRESHOLD:
                ok = True
        if not ok:
            # 回退
            if remaining_tubes:
                fb = StrictPhasedAlgorithm()
                extra, remain, _, _ = fb.generate(
                    remaining_tubes=remaining_tubes, raw_length=raw_length,
                    start_plan_id=plan_id, leftovers=leftovers, max_plans=max_plans)
                cutting_plans.extend(extra)
                remaining_tubes = remain
            return cutting_plans, remaining_tubes, leftovers, plan_id

        # 逐型号组构造(同型号才能拼接); 无法构造的型号组交回退
        K = raw_length // L
        rem = raw_length - K * L
        recv_len = L - rem  # 枢纽接收段长度
        max_recv_per_hub = (raw_length - (K - 1) * L) // recv_len  # 枢纽最多接收段数

        built_any = False
        for key, tubes in groups.items():
            N = len(tubes)
            T = -(-N * L // raw_length)  # ceil
            D = N - T * K
            if D <= 0:
                continue  # 全整管, 交回退做完美
            if max_recv_per_hub < 1:
                continue
            # 最小 s: 从 D 起递增, 找到可分配的
            s = None
            H = None
            for s_try in range(D, N + 1):
                H_try = s_try - D
                if H_try < 1 or H_try > T:
                    continue
                # s_try 个接收段分到 H_try 个枢纽, 每枢纽 <= max_recv_per_hub
                if s_try <= H_try * max_recv_per_hub:
                    # 端管数 E=s_try, 纯管 P=T-s_try-H_try >=0
                    if T - s_try - H_try >= 0:
                        s = s_try
                        H = H_try
                        break
            if s is None:
                continue
            E = s
            P = T - s - H
            if E + H + P != T or P < 0:
                continue

            # 取出该型号组的管(按顺序)
            tube_width = tubes[0]['tube_width']
            yield_force = tubes[0].get('yield_force')
            product_length = tubes[0].get('product_length')
            local = list(tubes)
            idx = 0

            def take():
                nonlocal idx
                t = local[idx]
                idx += 1
                return t

            # 1) E 个端管(宿主/host): K 整 + R(rem)余料段, 由 provider 提供 recv_len 拼成 L
            #    端管产出 K 整管并留下 R 余料, 是拼接关系中的「主」, 标注应在此段。
            end_ids = []
            for _ in range(E):
                ets = []
                for _ in range(K):
                    b = take()
                    ets.append({'tube_length': L, 'product_length': product_length,
                                'yield_force': yield_force, 'tube_width': tube_width})
                ets.append({'tube_length': rem, 'product_length': product_length,
                            'yield_force': yield_force, 'tube_width': tube_width,
                            'spliced_from': recv_len, 'original_length': L,
                            'host_role': 'host'})
                plan = {
                    'plan_id': plan_id, 'tube_width': tube_width,
                    'raw_length': raw_length, 'remaining_length': 0,
                    'tubes': ets, 'pieces': len(ets), 'raw_materials': 1,
                    'splice': True,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': 'hub_host',
                }
                cutting_plans.append(plan)
                end_ids.append(plan_id)
                plan_id += 1

            # 2) H 个枢纽管(供给/provider): (K-1) 整 + n_i 个 recv_len 供给段, 配对端管的 R
            # 分配 n_i: 尽量均匀, 每个 <= max_recv_per_hub
            base = s // H
            extra = s % H
            # 端管按顺序配给枢纽
            end_ptr = 0
            for h in range(H):
                n_i = base + (1 if h < extra else 0)
                hts = []
                for _ in range(K - 1):
                    hts.append({'tube_length': L, 'product_length': product_length,
                                'yield_force': yield_force, 'tube_width': tube_width})
                for _ in range(n_i):
                    hts.append({'tube_length': recv_len, 'product_length': product_length,
                                'yield_force': yield_force, 'tube_width': tube_width,
                                'host_role': 'provider', 'pair_length': rem,
                                'original_length': L})
                used = (K - 1) * L + n_i * recv_len
                rem_len = raw_length - used
                # 该枢纽配对的端管(用于 splice_info 关联)
                paired_end = end_ids[end_ptr] if end_ptr < len(end_ids) else None
                end_ptr += n_i
                plan = {
                    'plan_id': plan_id, 'tube_width': tube_width,
                    'raw_length': raw_length, 'remaining_length': rem_len,
                    'tubes': hts, 'pieces': len(hts), 'raw_materials': 1,
                    'splice': True,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0,
                                    'provider_for_hosts': [paired_end] if paired_end else []},
                    'perfect_source': 'hub_provider',
                }
                if rem_len > SPLICE_THRESHOLD:
                    plan['splice_info']['to_plan'] = plan_id + 1
                    plan['splice_info']['length'] = rem_len
                cutting_plans.append(plan)
                plan_id += 1

            # 3) P 个纯管: K 整, remaining=rem(孤岛余料, 放宽校验接受)
            for _ in range(P):
                pts = []
                for _ in range(K):
                    pts.append({'tube_length': L, 'product_length': product_length,
                                'yield_force': yield_force, 'tube_width': tube_width})
                plan = {
                    'plan_id': plan_id, 'tube_width': tube_width,
                    'raw_length': raw_length, 'remaining_length': rem,
                    'tubes': pts, 'pieces': len(pts), 'raw_materials': 1,
                    'splice': False,
                    'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0},
                    'perfect_source': 'normal' if rem <= SPLICE_THRESHOLD else None,
                }
                cutting_plans.append(plan)
                plan_id += 1

            # 该型号组已消费 N 根, 从 remaining_tubes 移除
            remaining_tubes = [t for t in remaining_tubes
                              if not (t['tube_length'] == L
                                      and t.get('yield_force') == yield_force
                                      and t.get('product_length') == product_length)]
            # 移除前 N 根(按数量)
            cnt = N
            new_rem = []
            for t in remaining_tubes:
                if cnt > 0 and t['tube_length'] == L and t.get('yield_force') == yield_force and t.get('product_length') == product_length:
                    cnt -= 1
                    continue
                new_rem.append(t)
            remaining_tubes = new_rem
            built_any = True

        # 未被构造覆盖的(非该长度或条件不满足)交回退
        if remaining_tubes:
            fb = StrictPhasedAlgorithm()
            extra, remain, _, _ = fb.generate(
                remaining_tubes=remaining_tubes, raw_length=raw_length,
                start_plan_id=plan_id, leftovers=leftovers, max_plans=max_plans)
            cutting_plans.extend(extra)
            remaining_tubes = remain

        logging.info("枢纽图算法 - 构造: %s", built_any)
        return cutting_plans, remaining_tubes, leftovers, plan_id


class StrictPhasedAlgorithm(CuttingAlgorithmBase):
    """
    严格三阶段算法（含阶段 1.5）：
      阶段一：完美切割。在不引入拼接前提下，最大化“余料 <= SPLICE_THRESHOLD”的原材数量。
      阶段 1.5：当库存仅剩两种产品长度时，优先「逐根拼接消耗两种规格 → 余量只剩一种规格时择优收尾」，
              单规格且宿主模板有效时并行候选 plain / host，合法且更优（更少续接链、余料更小）时优先宿主，
              使图面结构清晰。若无法推进则整体退回，交由阶段二处理。
      阶段二：严格拼接链。复用 legacy + 链路重组 / 尾段多算法竞选。
      阶段三：宿主-供给。剩余仅一种型号时，复用单规格择优收尾（plain / host 竞选）。
      最后可按 ENABLE_SEGMENT_BORROW_REPAIR 触发段借出修复（兜底，默认关闭）。
    并联择优顺序（在 TubeLayoutGenerator 中）：合法 -> 拼接次数 -> 无拼接完美数 -> 总余料 -> 原材根数。
    """

    name = "strict_phased"

    def __init__(self,
                 max_perfect_subset_size=6,
                 max_perfect_branches=4096,
                 max_chain_starters=64,
                 max_chain_depth=80,
                 max_chain_branches=8192):
        self.max_perfect_subset_size = max_perfect_subset_size
        self.max_perfect_branches = max_perfect_branches
        self.max_chain_starters = max_chain_starters
        self.max_chain_depth = max_chain_depth
        self.max_chain_branches = max_chain_branches
        self.last_run_stats = {
            "phase1_raw": 0,
            "phase15_raw": 0,
            "phase2_raw": 0,
            "phase3_raw": 0,
            "perfect_cuts": 0,
            "splice_count": 0,
            "total_waste": 0
        }

    @staticmethod
    def _length_pool(tubes):
        pool = {}
        for i, t in enumerate(tubes):
            pool.setdefault(t['tube_length'], []).append(i)
        return pool

    @staticmethod
    def _make_plan(plan_id, raw_length, used_tubes_meta, splice_segment, leftover, splice_info_extra=None):
        """
        used_tubes_meta: list of full tube dicts (含 tube_width 等)
        splice_segment: None 或 {'tube_length': R, 'spliced_from': prev_leftover, 'original_length': L, 'product_length': pl, 'yield_force': yf, 'tube_width': tw}
        leftover: 当前原材的余量
        """
        tubes = []
        if splice_segment is not None:
            tubes.append(splice_segment)
        tubes.extend(used_tubes_meta)
        first = (splice_segment or used_tubes_meta[0]) if (splice_segment or used_tubes_meta) else {}
        plan = {
            'plan_id': plan_id,
            'tube_width': first.get('tube_width', 0),
            'raw_length': raw_length,
            'remaining_length': leftover,
            'tubes': tubes,
            'pieces': len(tubes),
            'raw_materials': 1,
            'splice': splice_segment is not None,
            'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0}
        }
        if splice_info_extra:
            plan['splice_info'].update(splice_info_extra)
        return plan

    def _find_perfect_combo(self, length_counts, raw_length, preferred_length_combos=None):
        """在 length_counts (dict: length -> count) 中找一个组合 ∑ ∈ [raw_length-阈值, raw_length]。
        返回 (combo_dict: {length: take_count}, used_sum, num_pieces) 或 None。
        优先：剩余 <= 阈值且尽量少件数 + 余料尽量小；质量并列时偏好已出现过的长度组合。
        """
        lengths = sorted([L for L in length_counts if length_counts[L] > 0], reverse=True)
        if not lengths:
            return None

        preferred = preferred_length_combos or set()
        best = {'combo': None, 'sum': -1, 'pieces': 10 ** 9, 'prefer': 1}
        branches = [0]

        def dfs(idx, current_sum, current_combo, pieces):
            if branches[0] >= self.max_perfect_branches:
                return
            branches[0] += 1
            if pieces > self.max_perfect_subset_size:
                return
            if current_sum > raw_length:
                return
            leftover = raw_length - current_sum
            if leftover <= SPLICE_THRESHOLD and pieces > 0:
                prefer = 0 if _length_combo_key(current_combo) in preferred else 1
                better = (
                    best['sum'] < 0
                    or pieces < best['pieces']
                    or (pieces == best['pieces'] and current_sum > best['sum'])
                    or (pieces == best['pieces'] and current_sum == best['sum'] and prefer < best['prefer'])
                )
                if better:
                    best['combo'] = dict(current_combo)
                    best['sum'] = current_sum
                    best['pieces'] = pieces
                    best['prefer'] = prefer
            if idx >= len(lengths):
                return
            L = lengths[idx]
            avail = length_counts[L] - current_combo.get(L, 0)
            max_take = min(avail, (raw_length - current_sum) // L)
            for k in range(max_take, -1, -1):
                if k > 0:
                    current_combo[L] = current_combo.get(L, 0) + k
                    dfs(idx + 1, current_sum + L * k, current_combo, pieces + k)
                    current_combo[L] -= k
                    if current_combo[L] == 0:
                        del current_combo[L]
                else:
                    dfs(idx + 1, current_sum, current_combo, pieces)

        dfs(0, 0, {}, 0)
        if best['combo'] is None:
            return None
        return best['combo'], best['sum'], best['pieces']

    def _consume_combo(self, remaining_tubes, combo):
        """从 remaining_tubes 中按 combo 取出对应根数，返回 used_meta + 修改后的 remaining_tubes。
        按池内顺序取同长度管（FIFO），不跨型号重排，避免拆散本可合并的同型号链。
        """
        used = []
        for L, take in combo.items():
            taken = 0
            i = 0
            while taken < take and i < len(remaining_tubes):
                if remaining_tubes[i]['tube_length'] == L:
                    used.append(remaining_tubes.pop(i))
                    taken += 1
                else:
                    i += 1
        return used, remaining_tubes

    def _phase1_perfect_cuts(self, remaining_tubes, raw_length, plan_id):
        plans = []
        preferred = set()
        while remaining_tubes:
            counts = {}
            for t in remaining_tubes:
                counts[t['tube_length']] = counts.get(t['tube_length'], 0) + 1
            res = self._find_perfect_combo(counts, raw_length, preferred)
            if res is None:
                break
            combo, used_sum, _ = res
            used, remaining_tubes = self._consume_combo(remaining_tubes, combo)
            leftover = raw_length - used_sum
            plan = self._make_plan(plan_id, raw_length, used, None, leftover)
            plan['perfect_source'] = "phase1"
            plans.append(plan)
            combo_key = _length_combo_key(combo)
            if combo_key:
                preferred.add(combo_key)
            plan_id += 1
        return plans, remaining_tubes, plan_id

    def _splice_partner_exists(self, leftover, length_counts):
        """检查池中是否存在长度 L 满足 L > leftover 且 L - leftover > SPLICE_THRESHOLD。"""
        if leftover <= 0:
            return False
        for L, c in length_counts.items():
            if c <= 0:
                continue
            if L > leftover and (L - leftover) > SPLICE_THRESHOLD:
                return True
        return False

    @staticmethod
    def _host_template_valid(L, raw_length):
        K = raw_length // L
        R = raw_length - K * L
        P = L - R if L > R else 0
        valid = K > 0 and R > SPLICE_THRESHOLD and P > SPLICE_THRESHOLD
        return valid, K, R, P

    @staticmethod
    def _tube_inventory_length(tube):
        if tube.get('host_role') == 'provider':
            return None
        if 'spliced_from' in tube:
            return tube.get('original_length') or tube.get('nominal_tube_length')
        return tube.get('tube_length')

    @staticmethod
    def _recover_tubes_from_plans(plans):
        recovered = []
        for p in plans:
            for t in p.get('tubes', []):
                tl = StrictPhasedAlgorithm._tube_inventory_length(t)
                if tl is None or tl <= 0:
                    continue
                recovered.append({
                    'tube_length': tl,
                    'tube_width': t.get('tube_width'),
                    'product_length': t.get('product_length'),
                    'yield_force': t.get('yield_force'),
                })
        return recovered

    def _plan_uses_only_length(self, plan, L):
        tubes = [t for t in plan.get('tubes', []) if t.get('host_role') != 'provider']
        if not tubes:
            return False
        return all(self._tube_inventory_length(t) == L for t in tubes)

    def _fix_mixed_plan_after_L_reclaim(self, plan, raw_length):
        """回收纯 L 链式方案后，将混合方案重整为本根原材上的实切（按库存长度去重）。"""
        q = copy.deepcopy(plan)
        q['splice_info'] = {'from_plan': None, 'to_plan': None, 'length': 0}
        rebuilt = []
        for t in q.get('tubes', []):
            if t.get('host_role') == 'provider':
                continue
            inv = self._tube_inventory_length(t)
            if not inv:
                continue
            rebuilt.append({
                'tube_length': inv,
                'tube_width': t.get('tube_width'),
                'product_length': t.get('product_length'),
                'yield_force': t.get('yield_force'),
            })
        q['tubes'] = rebuilt
        q['pieces'] = len(rebuilt)
        q['remaining_length'] = raw_length - sum(t['tube_length'] for t in rebuilt)
        q['splice'] = False
        return q

    def _reclaim_pure_L_plans(self, prior_plans, working, L, raw_length):
        """回收 prior 中纯 L 切割方案，保留其它长度方案并解除续接依赖。"""
        kept = []
        l_pool = list(working)
        for p in prior_plans:
            if self._plan_uses_only_length(p, L):
                l_pool.extend(self._recover_tubes_from_plans([p]))
            else:
                kept.append(self._fix_mixed_plan_after_L_reclaim(p, raw_length))
        return kept, l_pool

    def _append_other_length_tail_plans(self, other_tubes, raw_length, plan_id):
        """将非主规格余量方管切为方案，并强制排在最后（允许末根大余料）。"""
        if not other_tubes:
            return [], plan_id
        plans = []
        pool = copy.deepcopy(other_tubes)
        while pool:
            counts = {}
            for t in pool:
                counts[t['tube_length']] = counts.get(t['tube_length'], 0) + 1
            combo = self._find_perfect_combo(counts, raw_length)
            if combo:
                combo_dict, used_sum, _ = combo
                used, pool = self._consume_combo(pool, combo_dict)
                leftover = raw_length - used_sum
            else:
                t0 = pool.pop(0)
                used, used_sum = [t0], t0['tube_length']
                leftover = raw_length - used_sum
            plan = self._make_plan(plan_id, raw_length, used, None, leftover)
            plan['perfect_source'] = 'other_length_tail'
            plans.append(plan)
            plan_id += 1
        return plans, plan_id

    @staticmethod
    def _count_inter_plan_chain_links(plans):
        """非宿主-供给方案上的跨方案余料续接数（越少图面越整洁）。"""
        n = 0
        for p in plans:
            if any(t.get('host_role') in ('host', 'provider') for t in p.get('tubes', [])):
                continue
            if (p.get('splice_info') or {}).get('to_plan') is not None:
                n += 1
        return n

    @staticmethod
    def _single_spec_finish_rank(prior_plans, new_plans, raw_length, is_host):
        combined = prior_plans + new_plans
        is_ok, _violations = validate_strict_constraint(combined, raw_length)
        if not is_ok:
            return (1, 10 ** 9, 10 ** 9, 10 ** 9, 1 if is_host else 0)
        chain_links = StrictPhasedAlgorithm._count_inter_plan_chain_links(new_plans)
        waste = sum_scoring_waste(combined)
        raw_n = sum(p.get('raw_materials', 1) for p in new_plans)
        # 合法时：优先宿主（图面结构清晰）→ 少续接链 → 余料 → 原材根数
        return (0, 0 if is_host else 1, chain_links, waste, raw_n)

    def _resolve_single_spec_finish(self, prior_plans, working, leftovers_acc, raw_length, plan_id):
        """
        单规格大量收尾：宿主模板有效且根数 ≥ K+1 时，回滚 prior 中同规格链式切法，
        同时候选 plain / host 并择优；合法时优先宿主以保持图面结构清晰。
        """
        if not working:
            return [], working, leftovers_acc, plan_id

        L = working[0]['tube_length']
        count = len(working)
        valid, K, _R, _P = self._host_template_valid(L, raw_length)
        lo_try = list(leftovers_acc)
        candidates = []

        compare_prior = list(prior_plans)
        compare_working = list(working)
        other_tail = []
        did_rollback = False
        # 失败时需返回的「全部待切管」：默认等于 working；若发生回滚，则等于从 prior 回收的管 + working。
        # 否则回滚回收的管子会丢失（既不在返回的方案里，也不在返回的 working 里），导致后续阶段少切管。
        all_rec = list(working)
        if valid and count >= K + 1 and prior_plans:
            all_rec = self._recover_tubes_from_plans(prior_plans) + list(working)
            other_tail = [t for t in all_rec if t['tube_length'] != L]
            compare_working = [t for t in all_rec if t['tube_length'] == L]
            compare_prior = []
            count = len(compare_working)
            did_rollback = True
            logging.info(
                '单规格宿主收尾：回滚阶段方案，L=%s %s 根，其它规格 %s 根',
                L, count, len(other_tail),
            )

        finish_lo = [] if did_rollback else lo_try

        def _pack_finish(core_plans, pid, remain_tubes, lo_out, is_host, append_other_tail=False):
            packed = list(core_plans)
            pid_out = pid
            rank_plans = packed
            if append_other_tail and other_tail and not remain_tubes:
                tail, pid_out = self._append_other_length_tail_plans(
                    other_tail, raw_length, pid_out
                )
                packed.extend(tail)
                rank_plans = packed
            rank = self._single_spec_finish_rank(
                compare_prior, rank_plans, raw_length, is_host
            )
            return rank, packed, remain_tubes, lo_out, pid_out

        plain_algo = NormalDeepThenGreedyAlgorithm()

        if valid and count >= K + 1:
            hp = HostProviderAlgorithm()
            hp_plans, remain_hp, lo_hp, pid_hp = hp.generate(
                remaining_tubes=copy.deepcopy(compare_working),
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=finish_lo,
                max_plans=None,
            )
            if hp_plans:
                defer_other = bool(other_tail and remain_hp)
                rank, packed, rem, lo, pid = _pack_finish(
                    hp_plans, pid_hp, remain_hp, lo_hp, True,
                    append_other_tail=not defer_other,
                )
                if rank[0] == 0:
                    if defer_other:
                        rem = list(rem) + list(other_tail)
                    candidates.append(('host', rank, packed, rem, lo, pid))

        plain_plans, remain_plain, _, pid_plain = plain_algo.generate(
            remaining_tubes=copy.deepcopy(compare_working),
            raw_length=raw_length,
            start_plan_id=plan_id,
            leftovers=finish_lo,
            max_plans=None,
        )
        if not remain_plain and plain_plans:
            rank, packed, rem, lo, pid = _pack_finish(
                plain_plans, pid_plain, [], [], False,
                append_other_tail=bool(other_tail),
            )
            if rank[0] == 0:
                candidates.append(('plain', rank, packed, rem, lo, pid))

        if candidates:
            name, rank, chosen_plans, remain_out, chosen_lo, chosen_pid = min(
                candidates, key=lambda x: x[1]
            )
            logging.info(
                '单规格收尾择优: %s (L=%s, 根数=%s, 续接链=%s, 评分=%s)',
                name, L, count, rank[2], rank,
            )
            return compare_prior + chosen_plans, remain_out, chosen_lo, chosen_pid

        if valid and count >= K + 1:
            hp = HostProviderAlgorithm()
            hp_plans, remain, lo, pid = hp.generate(
                remaining_tubes=compare_working,
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=finish_lo,
                max_plans=None,
            )
            if hp_plans:
                defer_other = bool(other_tail and remain)
                rank, packed, remain, lo, pid = _pack_finish(
                    hp_plans, pid, remain, lo, True,
                    append_other_tail=not defer_other,
                )
                if rank[0] == 0:
                    if defer_other:
                        remain = list(remain) + list(other_tail)
                    return compare_prior + packed, remain, lo, pid

        if plain_plans and not remain_plain:
            rank, packed, _, lo, pid = _pack_finish(
                plain_plans, pid_plain, remain_plain, lo_try, False,
                append_other_tail=bool(other_tail),
            )
            if rank[0] == 0:
                return compare_prior + packed, remain_plain, lo, pid

        # 失败时返回 all_rec（含从 prior 回滚回收的管），保证不丢管；无回滚时 all_rec == working。
        return [], all_rec, leftovers_acc, plan_id

    def _phase15_dual_splice_then_host(self, remaining_tubes, raw_length, plan_id):
        """
        阶段 1.5：仅剩两种产品长度时，用 legacy 算法每次只生成 1 根原材方案，保留 leftovers 拼接链，
        直到池中只剩一种长度，再对剩余库存做 plain / host 择优收尾。
        任一步无法继续则放弃本阶段（返回空方案列表，inventory 与 plan_id 保持调用前状态）。
        """
        if not remaining_tubes:
            return [], remaining_tubes, plan_id
        uniq_lengths = {t['tube_length'] for t in remaining_tubes}
        if len(uniq_lengths) != 2:
            return [], remaining_tubes, plan_id

        start_plan_id = plan_id
        stock_snapshot = copy.deepcopy(remaining_tubes)
        plans_acc = []
        working = copy.deepcopy(remaining_tubes)
        leftovers_acc: List[int] = []
        algo = NormalDeepThenGreedyAlgorithm()
        guard = 0

        while len({t['tube_length'] for t in working}) >= 2:
            guard += 1
            if guard > 600:
                logging.info('阶段1.5 双规格：防护退出，退回阶段二')
                return [], stock_snapshot, start_plan_id
            chunk, working, leftovers_acc, plan_id = algo.generate(
                remaining_tubes=working,
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=leftovers_acc,
                max_plans=1,
            )
            if not chunk:
                logging.info('阶段1.5 双规格：无法生成下一根原材方案，退回阶段二')
                return [], stock_snapshot, start_plan_id
            plans_acc.extend(chunk)

        guard2 = 0
        while leftovers_acc:
            guard2 += 1
            if guard2 > 200:
                logging.info('阶段1.5：leftovers 清理超时，退回阶段二')
                return [], stock_snapshot, start_plan_id
            chunk, working, leftovers_acc, plan_id = algo.generate(
                remaining_tubes=working,
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=leftovers_acc,
                max_plans=1,
            )
            if not chunk:
                logging.info('阶段1.5：leftovers 无法承接，退回阶段二')
                return [], stock_snapshot, start_plan_id
            plans_acc.extend(chunk)

        if working:
            finish_plans, working, leftovers_acc, plan_id = self._resolve_single_spec_finish(
                plans_acc, working, leftovers_acc, raw_length, plan_id,
            )
            plans_acc = finish_plans

        if working:
            logging.info(
                '阶段1.5：宿主后仍有剩余方管 %s 根，交给阶段二继续',
                len(working),
            )

        logging.info(
            '阶段1.5 完成（双规格→宿主）：长度集合 %s → 生成 %s 根原材方案，宿主后剩余方管 %s',
            sorted(uniq_lengths),
            len(plans_acc),
            len(working),
        )
        return plans_acc, working, plan_id

    def _phase2_via_legacy_with_repair(self, remaining_tubes, raw_length, plan_id):
        """阶段二：单规格优先四段拼接链；否则复用 NormalDeepThenGreedy + 阶梯重组修复。"""
        if not remaining_tubes:
            return [], remaining_tubes, plan_id

        chain_algo = UniformFourBarChainAlgorithm()
        if UniformFourBarChainAlgorithm._can_apply(remaining_tubes, raw_length):
            working = copy.deepcopy(remaining_tubes)
            plans, remain, _, plan_id = chain_algo.generate(
                remaining_tubes=working,
                raw_length=raw_length,
                start_plan_id=plan_id,
                leftovers=[],
                max_plans=None,
            )
            if plans and not remain:
                is_ok, viols = validate_strict_constraint(plans, raw_length)
                if is_ok:
                    logging.info(
                        "阶段二：单规格四段链 %s 根原材, 拼接 %s 次",
                        len(plans),
                        sum(1 for p in plans for t in p['tubes'] if 'spliced_from' in t),
                    )
                    return plans, remain, plan_id
                logging.info(
                    "阶段二：四段链未过检(违规 %s)，回退贪心",
                    len(viols),
                )

        base_algo = NormalDeepThenGreedyAlgorithm()
        working = copy.deepcopy(remaining_tubes)
        plans, remain, _, plan_id = base_algo.generate(
            remaining_tubes=working,
            raw_length=raw_length,
            start_plan_id=plan_id,
            leftovers=[],
            max_plans=None
        )

        # 阶梯式重组：每个层级最多 max_rounds 轮，整体每轮都重组失败/不改善则升级
        # 不再做 full_group（成本过高，对 100 个方案的 GreedyThenDeep 重排单次就要数十秒）
        levels = [
            ("connected_component", None, 3),
            ("neighborhood", 3, 2),    # 前后各扩展 3 个方案
            ("neighborhood", 8, 2),    # 前后各扩展 8 个方案
        ]
        for scope_kind, param, max_rounds in levels:
            prev_score = None
            for _round in range(max_rounds):
                is_valid, violations = validate_strict_constraint(plans, raw_length)
                if is_valid or not violations:
                    break
                cur_score = (len(violations),) + self._score_plans(plans, raw_length)
                if prev_score is not None and cur_score >= prev_score:
                    break
                new_plans, remain, plan_id = self._repair_violations(
                    plans, violations, remain, raw_length, plan_id,
                    scope_kind=scope_kind, scope_param=param
                )
                if new_plans is plans:
                    break
                plans = new_plans
                prev_score = cur_score
            is_valid, _ = validate_strict_constraint(plans, raw_length)
            if is_valid:
                break

        # 收尾修复：违规及之后整段回收 + 多算法竞选（包含 HostProvider）
        plans, plan_id = self._finalize_tail_with_multi_algo(plans, raw_length, plan_id)

        return plans, remain, plan_id

    def _finalize_tail_with_multi_algo(self, plans, raw_length, plan_id):
        """对仍有违规的 width 组：
        scope = "第一个违规及之后所有方案" -> 整段回收（拼接段还原为完整长度）-> 用
        GreedyThenDeep / NormalDeepThenGreedy / HostProvider 多算法竞选重切，
        仅当评分严格改善时采用。

        对应用户策略："先把多种长度方管做组合拼接，剩余单一长度走宿主-供给"。
        - NormalDeepThenGreedy / GreedyThenDeep 负责多长度组合
        - HostProvider 负责单一长度高效收尾
        """
        is_valid, violations = validate_strict_constraint(plans, raw_length)
        logging.info(
            "尾段重切入口：is_valid=%s, 违规数=%s, plans=%s",
            is_valid, len(violations), len(plans)
        )
        if is_valid or not violations:
            return plans, plan_id

        plan_by_id = {p['plan_id']: p for p in plans}
        by_width = {}
        for p in plans:
            by_width.setdefault(p.get('tube_width'), []).append(p)

        changed = False
        cur_violations_total = len(violations)
        cur_waste = sum(v[1] for v in violations)

        logging.info(
            "尾段重切：by_width keys=%s, violations=%s",
            list(by_width.keys()),
            [(v[0], v[1]) for v in violations]
        )

        for width, group in by_width.items():
            sorted_group = sorted(group, key=lambda x: x.get('plan_id', 0))
            group_violation_ids = {
                v[0] for v in violations
                if plan_by_id.get(v[0], {}).get('tube_width') == width
            }
            if not group_violation_ids:
                continue

            first_violation_idx = min(
                i for i, p in enumerate(sorted_group)
                if p['plan_id'] in group_violation_ids
            )
            scope = sorted_group[first_violation_idx:]
            scope_ids = {p['plan_id'] for p in scope}
            logging.info(
                "  尾段重切 width=%s: 组内方案=%s, 违规=%s, scope=%s 个 (从 plan_id=%s 开始)",
                width, len(sorted_group), group_violation_ids,
                len(scope), scope[0]['plan_id']
            )

            # 含 host_role 的不能拆
            if any(t.get('host_role') in ('provider', 'host')
                   for p in scope for t in p.get('tubes', [])):
                logging.info("    跳过：scope 含 host_role 段")
                continue

            # 检查 scope[0] 是否有上游 carry-in（spliced_from）
            # 若有，需要把上游"提供者"方案也回收，否则上游余料失去消费者
            extended_scope_ids = set(scope_ids)
            first_plan = scope[0]
            for t in first_plan.get('tubes', []):
                if 'spliced_from' in t:
                    from_pid = first_plan.get('splice_info', {}).get('from_plan')
                    if from_pid is not None and from_pid in plan_by_id:
                        extended_scope_ids.add(from_pid)

            # 重新构造 extended_scope（按 plan_id 排序）
            extended_scope = [
                p for p in sorted_group
                if p['plan_id'] in extended_scope_ids
            ]
            # 检查扩展后是否仍是连续后缀（不连续就跳过避免破坏前序拼接关系）
            min_idx = min(
                i for i, p in enumerate(sorted_group)
                if p['plan_id'] in extended_scope_ids
            )
            if any(p['plan_id'] not in extended_scope_ids
                   for p in sorted_group[min_idx:]):
                logging.info("    跳过：extended_scope 不是连续后缀")
                continue

            # 排除含 host_role 的（扩展后再次检查）
            if any(t.get('host_role') in ('provider', 'host')
                   for p in extended_scope for t in p.get('tubes', [])):
                logging.info("    跳过：extended_scope 含 host_role 段")
                continue

            # 上游再扩展：如果 extended_scope[0] 仍有 spliced_from，再往前一根
            # 简化处理：只往前扩 1 层；多层 carry-in 罕见
            head = extended_scope[0]
            head_splices = [
                (t.get('tube_length'), t.get('spliced_from'))
                for t in head.get('tubes', [])
                if 'spliced_from' in t
            ]
            logging.info(
                "    head=#%s, head_splices=%s, from_plan=%s",
                head.get('plan_id'), head_splices,
                head.get('splice_info', {}).get('from_plan')
            )
            if any('spliced_from' in t for t in head.get('tubes', [])):
                from_pid = head.get('splice_info', {}).get('from_plan')
                if from_pid is not None and from_pid in plan_by_id:
                    if any('spliced_from' in t
                           for t in plan_by_id[from_pid].get('tubes', [])):
                        logging.info("    跳过：二阶 carry-in")
                        continue
                    else:
                        # head 有 spliced_from 但上游没有；把上游也加入 extended_scope
                        extended_scope_ids.add(from_pid)
                        extended_scope = [
                            p for p in sorted_group
                            if p['plan_id'] in extended_scope_ids
                        ]
                        head = extended_scope[0]
                        logging.info(
                            "    一阶 carry-in，再次扩展到 #%s",
                            head.get('plan_id')
                        )

            # 回收 extended_scope 内所有方管段（拼接段还原为 original_length）
            recovered = []
            for p in extended_scope:
                for t in p.get('tubes', []):
                    tl = t.get('original_length') if 'spliced_from' in t else t.get('tube_length')
                    if tl is None or tl <= 0:
                        continue
                    recovered.append({
                        'tube_length': tl,
                        'tube_width': t.get('tube_width', width),
                        'product_length': t.get('product_length'),
                        'yield_force': t.get('yield_force'),
                    })

            if not recovered:
                logging.info("    跳过：回收空")
                continue

            # 规模保护
            if len(extended_scope) > 60:
                logging.info("    跳过：scope 过大 (%s)", len(extended_scope))
                continue

            kept_plans = [p for p in plans if p['plan_id'] not in extended_scope_ids]
            max_kept_id = max((p['plan_id'] for p in kept_plans), default=0)

            candidate_algos = [
                ('greedy_then_deep', GreedyThenDeepAlgorithm()),
                ('normal_deep_then_greedy', NormalDeepThenGreedyAlgorithm()),
                ('host_provider', HostProviderAlgorithm()),
            ]

            scope_old_violations = sum(
                1 for v in violations
                if plan_by_id.get(v[0], {}).get('tube_width') == width
            )
            old_full_score = (cur_violations_total, cur_waste) + \
                             self._score_plans(plans, raw_length)[1:]
            best_candidate = None
            best_full_score = old_full_score
            best_new_pid = plan_id
            best_name = None
            # 统计回收池长度分布
            len_dist = {}
            for t in recovered:
                len_dist[t['tube_length']] = len_dist.get(t['tube_length'], 0) + 1
            logging.info(
                "尾段重切 scope[width=%s]: 方案数=%s, 回收方管=%s 段, 长度分布=%s, 原评分=%s",
                width, len(extended_scope), len(recovered), len_dist, old_full_score
            )
            uniq_rec = {t['tube_length'] for t in recovered}
            if len(uniq_rec) == 2:
                p15_tail, rem15, pid15 = self._phase15_dual_splice_then_host(
                    copy.deepcopy(recovered),
                    raw_length,
                    max_kept_id + 1,
                )
                if p15_tail and not rem15:
                    cand15 = kept_plans + p15_tail
                    _, new_viol15 = validate_strict_constraint(cand15, raw_length)
                    sc15 = (
                        len(new_viol15), sum(v[1] for v in new_viol15)
                    ) + self._score_plans(cand15, raw_length)[1:]
                    logging.info(
                        "  [phase15_dual_host_tail] 新评分=%s (vs old=%s)",
                        sc15, old_full_score
                    )
                    if sc15 < best_full_score:
                        best_full_score = sc15
                        best_candidate = cand15
                        best_new_pid = pid15
                        best_name = 'phase15_dual_host_tail'

            for algo_name, algo in candidate_algos:
                new_plans, new_remain, _, new_plan_id = algo.generate(
                    remaining_tubes=copy.deepcopy(recovered),
                    raw_length=raw_length,
                    start_plan_id=max_kept_id + 1,
                    leftovers=[],
                    max_plans=None
                )
                if new_remain:
                    logging.info("  [%s] 未覆盖完成，剩余 %s 段", algo_name, len(new_remain))
                    continue
                candidate = kept_plans + new_plans
                _, new_viol = validate_strict_constraint(candidate, raw_length)
                new_full_score = (
                    len(new_viol), sum(v[1] for v in new_viol)
                ) + self._score_plans(candidate, raw_length)[1:]
                logging.info("  [%s] 新评分=%s (vs old=%s)", algo_name, new_full_score, old_full_score)
                if new_full_score < best_full_score:
                    best_full_score = new_full_score
                    best_candidate = candidate
                    best_new_pid = new_plan_id
                    best_name = algo_name

            if best_candidate is not None:
                logging.info(
                    "尾段重切生效[width=%s|%s]：违规 %s->%s, 违规额 %s->%s, scope=%s",
                    width, best_name,
                    old_full_score[0], best_full_score[0],
                    old_full_score[1], best_full_score[1],
                    len(extended_scope)
                )
                plans = best_candidate
                plan_id = best_new_pid
                plan_by_id = {p['plan_id']: p for p in plans}
                _, new_viol_global = validate_strict_constraint(plans, raw_length)
                cur_violations_total = len(new_viol_global)
                cur_waste = sum(v[1] for v in new_viol_global)
                violations = new_viol_global
                changed = True

        if changed:
            logging.info(
                "尾段重切总效果：违规 %s, 违规额 %s",
                cur_violations_total, cur_waste
            )
        return plans, plan_id

    def _attempt_segment_borrow(self, plans, raw_length, max_iter=20):
        """段借出修复：让孤岛违规方案 P 从其他方案 Q 借入一段方管 t，使 P 合法。
        - t.length ≤ P 余料 R，且 R - t.length ≤ SPLICE_THRESHOLD
        - 接受 Q 因此新违规，但只在总评分（违规数 + 全局废料 + 拼接数 + 原材数）严格改善时执行
        - 对当前数据集即"用 #1 的一段 2800 给 #94"这类局部修补
        - 每轮枚举所有 (violation, Q, t) 候选，挑评分最优的执行；循环直到无改善
        """
        for _iter in range(max_iter):
            is_valid, violations = validate_strict_constraint(plans, raw_length)
            if is_valid:
                break
            cur_violation_waste = sum(v[1] for v in violations)
            cur_rest = self._score_plans(plans, raw_length)
            cur_score = (len(violations), cur_violation_waste) + cur_rest[1:]
            best_score = cur_score
            best_op = None
            candidate_count = 0
            for vid, leftover, _reason in violations:
                p_idx = next((i for i, p in enumerate(plans) if p.get('plan_id') == vid), None)
                if p_idx is None:
                    continue
                P = plans[p_idx]
                target_w = P.get('tube_width')
                for q_idx, Q in enumerate(plans):
                    if q_idx == p_idx or Q.get('tube_width') != target_w:
                        continue
                    for t_idx, t in enumerate(Q.get('tubes', [])):
                        if 'spliced_from' in t or t.get('host_role') in ('provider', 'host'):
                            continue
                        L = t.get('tube_length', 0)
                        if L <= 0 or L > leftover:
                            continue
                        new_p_leftover = leftover - L
                        if new_p_leftover > SPLICE_THRESHOLD:
                            continue
                        candidate_count += 1
                        # 模拟交换
                        new_plans = copy.deepcopy(plans)
                        new_P = new_plans[p_idx]
                        new_Q = new_plans[q_idx]
                        removed = new_Q['tubes'].pop(t_idx)
                        new_Q['remaining_length'] = new_Q.get('remaining_length', 0) + L
                        new_Q['pieces'] = len(new_Q['tubes'])
                        new_P['tubes'].append(removed)
                        new_P['remaining_length'] = new_p_leftover
                        new_P['pieces'] = len(new_P['tubes'])
                        _, new_viol = validate_strict_constraint(new_plans, raw_length)
                        # 评分基准：违规数、违规额、再加 _score_plans（拼接数、原材数等）作为低优先项
                        new_violation_waste = sum(v[1] for v in new_viol)
                        rest = self._score_plans(new_plans, raw_length)
                        new_score = (len(new_viol), new_violation_waste) + rest[1:]
                        if new_score < best_score:
                            best_score = new_score
                            best_op = (p_idx, q_idx, t_idx, L, P.get('plan_id'),
                                       Q.get('plan_id'), leftover)
            if best_op is None:
                if candidate_count > 0:
                    logging.info(
                        "段借出修复：%s 个候选均未改善评分 (cur=%s)",
                        candidate_count, cur_score
                    )
                break
            p_idx, q_idx, t_idx, L, p_pid, q_pid, original_R = best_op
            P = plans[p_idx]
            Q = plans[q_idx]
            removed = Q['tubes'].pop(t_idx)
            Q['remaining_length'] = Q.get('remaining_length', 0) + L
            Q['pieces'] = len(Q['tubes'])
            P['tubes'].append(removed)
            P['remaining_length'] = P.get('remaining_length', 0) - L
            P['pieces'] = len(P['tubes'])
            logging.info(
                "段借出修复生效：P=#%s 余 %s -> %s, 借 Q=#%s 一段长 %s, 评分 %s -> %s",
                p_pid, original_R, P['remaining_length'], q_pid, L, cur_score, best_score
            )
        return plans

    def _select_scope_ids(self, plans, violation_ids, scope_kind, scope_param):
        """根据 scope_kind 选择要参与重排的方案 id 集合。"""
        plan_by_id = {p['plan_id']: p for p in plans}

        if scope_kind == "full_group":
            return set(plan_by_id.keys())

        if scope_kind == "neighborhood":
            sorted_ids = sorted(plan_by_id.keys())
            id_to_idx = {pid: idx for idx, pid in enumerate(sorted_ids)}
            n = scope_param or 0
            scope = set()
            for vid in violation_ids:
                if vid not in id_to_idx:
                    continue
                idx = id_to_idx[vid]
                lo = max(0, idx - n)
                hi = min(len(sorted_ids) - 1, idx + n)
                for k in range(lo, hi + 1):
                    scope.add(sorted_ids[k])
            return scope

        # connected_component 默认
        adj = {pid: set() for pid in plan_by_id}
        for p in plans:
            si = p.get('splice_info', {}) or {}
            for k in ('from_plan', 'to_plan'):
                v = si.get(k)
                if v in plan_by_id:
                    adj[p['plan_id']].add(v)
                    adj[v].add(p['plan_id'])
        scope = set()
        for vid in violation_ids:
            if vid in scope or vid not in plan_by_id:
                continue
            stack = [vid]
            while stack:
                x = stack.pop()
                if x in scope:
                    continue
                scope.add(x)
                stack.extend(adj.get(x, []))
        return scope

    def _repair_violations(self, plans, violations, leftover_pool, raw_length, plan_id,
                           scope_kind="connected_component", scope_param=None):
        """剥离指定 scope 的方案 -> 收集方管 -> 用 GreedyThenDeep 重排 -> 比较择优。"""
        violation_ids = {v[0] for v in violations}
        plan_by_id = {p['plan_id']: p for p in plans}

        scope_ids = self._select_scope_ids(plans, violation_ids, scope_kind, scope_param)
        # scope 必须包含全部违规方案，否则跳过
        if not scope_ids or any(vid not in scope_ids for vid in violation_ids):
            return plans, leftover_pool, plan_id

        # 规模保险：避免在过大范围跑深度搜索导致组合爆炸
        MAX_SCOPE_PLANS = 30
        if len(scope_ids) > MAX_SCOPE_PLANS:
            return plans, leftover_pool, plan_id

        # scope 的方案不能含 host_provider 的 provider/host 角色（否则 provider 段无法还原为需求）
        for pid in scope_ids:
            p = plan_by_id.get(pid)
            if p is None:
                continue
            for t in p.get('tubes', []):
                if t.get('host_role') in ('provider', 'host'):
                    return plans, leftover_pool, plan_id

        # 收集 scope 内所有方管
        recovered = []
        for pid in scope_ids:
            p = plan_by_id[pid]
            for t in p.get('tubes', []):
                tl = t.get('original_length') if 'spliced_from' in t else t.get('tube_length')
                if tl is None:
                    continue
                recovered.append({
                    'tube_length': tl,
                    'product_length': t.get('product_length'),
                    'yield_force': t.get('yield_force'),
                    'tube_width': t.get('tube_width')
                })

        if not recovered:
            return plans, leftover_pool, plan_id

        kept_plans = [p for p in plans if p['plan_id'] not in scope_ids]
        max_kept_id = max((p['plan_id'] for p in kept_plans), default=0)

        # 多算法竞选：GreedyThenDeep / NormalDeepThenGreedy / HostProvider 都尝试
        candidate_algos = [
            ('greedy_then_deep', GreedyThenDeepAlgorithm()),
            ('normal_deep_then_greedy', NormalDeepThenGreedyAlgorithm()),
            ('host_provider', HostProviderAlgorithm()),
        ]
        old_violation_waste = sum(v[1] for v in violations)
        old_score_full = (
            len(violations), old_violation_waste
        ) + self._score_plans(plans, raw_length)[1:]
        best_candidate = None
        best_score = old_score_full
        best_new_pid = plan_id
        best_name = None

        uniq_rec = {t['tube_length'] for t in recovered}
        if len(uniq_rec) == 2:
            p15_rep, rem15, pid15 = self._phase15_dual_splice_then_host(
                copy.deepcopy(recovered),
                raw_length,
                max_kept_id + 1,
            )
            if p15_rep and not rem15:
                cand15 = kept_plans + p15_rep
                _, new_viol15 = validate_strict_constraint(cand15, raw_length)
                new_vw15 = sum(v[1] for v in new_viol15)
                sc15 = (
                    len(new_viol15), new_vw15
                ) + self._score_plans(cand15, raw_length)[1:]
                if sc15 < best_score:
                    best_score = sc15
                    best_candidate = cand15
                    best_new_pid = pid15
                    best_name = 'phase15_dual_host_scope'

        for algo_name, algo in candidate_algos:
            new_plans, new_remain, _, new_plan_id = algo.generate(
                remaining_tubes=copy.deepcopy(recovered),
                raw_length=raw_length,
                start_plan_id=max_kept_id + 1,
                leftovers=[],
                max_plans=None
            )
            if new_remain:
                continue
            candidate = kept_plans + new_plans
            _, new_violations = validate_strict_constraint(candidate, raw_length)
            new_violation_waste = sum(v[1] for v in new_violations)
            new_score = (
                len(new_violations), new_violation_waste
            ) + self._score_plans(candidate, raw_length)[1:]
            if new_score < best_score:
                best_score = new_score
                best_candidate = candidate
                best_new_pid = new_plan_id
                best_name = algo_name

        if best_candidate is not None:
            logging.info(
                "链路重组生效[%s|%s|%s]：违规 %s->%s, 违规额 %s->%s, 范围 %s 方案",
                scope_kind, scope_param, best_name,
                old_score_full[0], best_score[0],
                old_score_full[1], best_score[1],
                len(scope_ids)
            )
            return best_candidate, leftover_pool, best_new_pid
        return plans, leftover_pool, plan_id

    @staticmethod
    def _score_plans(plans, raw_length):
        total_waste = sum_unused_leftover(plans)
        splice_count = sum(1 for p in plans for t in p['tubes'] if 'spliced_from' in t)
        return (total_waste, splice_count, len(plans))

    def _build_chain(self, length_counts, tube_meta_pool, raw_length, plan_id,
                     preferred_length_combos=None):
        """
        构造一条严格拼接链：起点 -> 若干消费 -> 终点（终余 <= 阈值）。
        length_counts: {L: count}（消耗后会被修改）
        tube_meta_pool: {L: [tube_dicts]}（消耗后会被修改）
        preferred_length_combos: 已出现长度组合，质量并列时优先复用。
        返回 (plans, plan_id) 或 (None, plan_id) 表示无法构造任何含拼接的链。
        若返回 plans=[]，表示当前池没有合理起点（应跳过链阶段）。
        """
        preferred_length_combos = preferred_length_combos if preferred_length_combos is not None else set()
        # 候选起点：寻找 leftover R ∈ (阈值, raw_length] 且存在可拼接对手 L>R 且 L-R>阈值。
        # 我们枚举若干起点尝试。
        starter_candidates = []
        # 起点用一组方管覆盖一根原材，剩余为 R
        # 简化：枚举 R 候选 = {L_i - L_j : L_i > L_j, L_i - L_j > 阈值} ∪ 单段后剩余
        sums_avail = []  # (used_sum, combo)
        avail_lengths = sorted([L for L, c in length_counts.items() if c > 0], reverse=True)

        # DFS 枚举若干小子集（深度 <= max_perfect_subset_size），收集 used_sum 候选
        collected = []
        branches = [0]

        def dfs(idx, current_sum, combo, pieces):
            if branches[0] >= self.max_perfect_branches or pieces > self.max_perfect_subset_size:
                return
            branches[0] += 1
            if current_sum > 0 and current_sum <= raw_length:
                R = raw_length - current_sum
                if R > SPLICE_THRESHOLD:
                    collected.append((current_sum, dict(combo), R))
            if idx >= len(avail_lengths):
                return
            L = avail_lengths[idx]
            avail = length_counts[L] - combo.get(L, 0)
            max_take = min(avail, (raw_length - current_sum) // L)
            for k in range(max_take, -1, -1):
                if k > 0:
                    combo[L] = combo.get(L, 0) + k
                    dfs(idx + 1, current_sum + L * k, combo, pieces + k)
                    combo[L] -= k
                    if combo[L] == 0:
                        del combo[L]
                else:
                    dfs(idx + 1, current_sum, combo, pieces)

        dfs(0, 0, {}, 0)

        # 过滤起点：必须存在拼接对手
        for used_sum, combo, R in collected:
            # 临时扣减计数检查对手
            for L, k in combo.items():
                length_counts[L] -= k
            ok = self._splice_partner_exists(R, length_counts)
            for L, k in combo.items():
                length_counts[L] += k
            if ok:
                starter_candidates.append((used_sum, combo, R))

        if not starter_candidates:
            return [], plan_id  # 让上层用兜底处理

        # 起点排序：余料越大、件数越少越优；质量并列时偏好已出现刀型
        starter_candidates.sort(
            key=lambda x: (
                -x[0],
                0 if _length_combo_key(x[1]) in preferred_length_combos else 1,
                len(x[1]),
            )
        )
        starter_candidates = starter_candidates[: self.max_chain_starters]

        for used_sum, combo, prev_leftover in starter_candidates:
            snap_counts = dict(length_counts)
            snap_pool = {k: list(v) for k, v in tube_meta_pool.items()}
            snap_plan_id = plan_id
            local_preferred = set(preferred_length_combos)

            chain_plans = []
            # 起点切割
            used_meta = self._take_from_pool(combo, tube_meta_pool, length_counts)
            starter_plan = self._make_plan(plan_id, raw_length, used_meta, None, prev_leftover)
            starter_plan['perfect_source'] = "phase2_starter"
            chain_plans.append(starter_plan)
            sk = _length_combo_key(combo)
            if sk:
                local_preferred.add(sk)
            plan_id += 1

            ok = True
            depth = 0
            while prev_leftover > SPLICE_THRESHOLD:
                depth += 1
                if depth > self.max_chain_depth:
                    ok = False
                    break
                # 选择拼接对手 L：L > prev_leftover 且 L - prev_leftover > 阈值
                partner_L = None
                # 优先剩余数量多的对手，便于继续构造
                for L in sorted(length_counts.keys(), key=lambda x: (-length_counts[x], -x)):
                    if length_counts[L] <= 0:
                        continue
                    if L > prev_leftover and (L - prev_leftover) > SPLICE_THRESHOLD:
                        partner_L = L
                        break
                if partner_L is None:
                    ok = False
                    break

                # 拿一根 partner_L 出来，切成 R + (L-R)：R=prev_leftover (已并入新原材的拼接段)
                partner_tube_dict = tube_meta_pool[partner_L].pop(0)
                length_counts[partner_L] -= 1
                splice_seg = {
                    'tube_length': partner_L - prev_leftover,
                    'spliced_from': prev_leftover,
                    'original_length': partner_L,
                    'product_length': partner_tube_dict.get('product_length'),
                    'yield_force': partner_tube_dict.get('yield_force'),
                    'tube_width': partner_tube_dict.get('tube_width')
                }
                # 把上一根的 to_plan 指向当前 plan_id
                chain_plans[-1]['splice_info']['to_plan'] = plan_id
                chain_plans[-1]['splice_info']['length'] = prev_leftover

                # 新原材剩余空间 = raw_length - splice_seg.tube_length
                space = raw_length - splice_seg['tube_length']

                # 在剩余空间内尽量多放方管，目标：终余 <= 阈值；否则保证终余可被下一根拼接
                used_now, used_sum_now = self._fill_space_with_constraint(
                    space, length_counts, tube_meta_pool, raw_length, local_preferred
                )
                next_leftover = space - used_sum_now

                # 严格约束：next_leftover 必须 <= 阈值 或 存在拼接对手
                if next_leftover > SPLICE_THRESHOLD and not self._splice_partner_exists(next_leftover, length_counts):
                    # 撤销本次填充与对手取出
                    for um in used_now:
                        tube_meta_pool[um['tube_length']].append(um)
                        length_counts[um['tube_length']] = length_counts.get(um['tube_length'], 0) + 1
                    tube_meta_pool[partner_L].insert(0, partner_tube_dict)
                    length_counts[partner_L] += 1
                    chain_plans[-1]['splice_info']['to_plan'] = None
                    chain_plans[-1]['splice_info']['length'] = 0
                    ok = False
                    break

                new_plan = self._make_plan(
                    plan_id, raw_length, used_now, splice_seg, next_leftover,
                    splice_info_extra={'from_plan': chain_plans[-1]['plan_id']}
                )
                new_plan['perfect_source'] = "phase2"
                chain_plans.append(new_plan)
                fk = _tubes_solid_length_combo(used_now)
                if fk:
                    local_preferred.add(fk)
                plan_id += 1
                prev_leftover = next_leftover

            if ok:
                preferred_length_combos.update(local_preferred)
                return chain_plans, plan_id
            # 回滚状态，尝试下一个起点
            length_counts.clear()
            length_counts.update(snap_counts)
            tube_meta_pool.clear()
            tube_meta_pool.update(snap_pool)
            plan_id = snap_plan_id

        return None, plan_id

    @staticmethod
    def _take_from_pool(combo, tube_meta_pool, length_counts):
        used_meta = []
        for L, k in combo.items():
            for _ in range(k):
                t = tube_meta_pool[L].pop(0)
                length_counts[L] -= 1
                used_meta.append(t)
        return used_meta

    def _fill_space_with_constraint(self, space, length_counts, tube_meta_pool, raw_length,
                                    preferred_length_combos=None):
        """
        在 [0, space] 空间内贪心选取若干方管，目标：尽量减小 leftover。
        但优先选 leftover 落入合法区间：要么 <= 阈值，要么 > 阈值且池中存在拼接对手。
        质量并列时偏好已出现过的长度组合。
        简化策略：从大到小贪心选；若结果违反约束，尝试少放一根。
        """
        preferred = preferred_length_combos or set()
        attempts = []  # (leftover, used_meta, used_sum)
        # 贪心 1：从大到小连续填
        used_meta, used_sum = self._greedy_fill(space, length_counts, tube_meta_pool, prefer="desc")
        attempts.append((space - used_sum, used_meta, used_sum))
        # 复原
        for um in used_meta:
            tube_meta_pool[um['tube_length']].append(um)
            length_counts[um['tube_length']] = length_counts.get(um['tube_length'], 0) + 1
        # 贪心 2：从小到大填，保留更多大件供下一根使用
        used_meta2, used_sum2 = self._greedy_fill(space, length_counts, tube_meta_pool, prefer="asc")
        attempts.append((space - used_sum2, used_meta2, used_sum2))
        # 选最优合法
        best = None
        for leftover, used, used_sum in attempts:
            # 合法性
            valid = leftover <= SPLICE_THRESHOLD or self._splice_partner_exists(leftover, length_counts_after(used, length_counts))
            combo_key = _tubes_solid_length_combo(used)
            prefer = 0 if (not preferred or combo_key in preferred) else 1
            score = (0 if valid else 1, leftover, prefer, -len(used))
            if best is None or score < best[0]:
                best = (score, leftover, used, used_sum)
        # 复原 attempts[1]
        for um in attempts[1][1]:
            tube_meta_pool[um['tube_length']].append(um)
            length_counts[um['tube_length']] = length_counts.get(um['tube_length'], 0) + 1
        # 重新执行选中的方案（实际从 pool 拿出）
        chosen_used = best[2]
        # 从池里重新弹出对应根数
        actual = []
        # 先按 length 计数
        need = {}
        for u in chosen_used:
            need[u['tube_length']] = need.get(u['tube_length'], 0) + 1
        for L, k in need.items():
            for _ in range(k):
                if not tube_meta_pool.get(L):
                    break
                t = tube_meta_pool[L].pop(0)
                length_counts[L] -= 1
                actual.append(t)
        return actual, sum(t['tube_length'] for t in actual)

    @staticmethod
    def _greedy_fill(space, length_counts, tube_meta_pool, prefer="desc"):
        used_meta = []
        used_sum = 0
        lengths = sorted([L for L in length_counts if length_counts[L] > 0],
                         reverse=(prefer == "desc"))
        for L in lengths:
            while length_counts.get(L, 0) > 0 and used_sum + L <= space:
                if not tube_meta_pool.get(L):
                    break
                t = tube_meta_pool[L].pop(0)
                length_counts[L] -= 1
                used_meta.append(t)
                used_sum += L
        return used_meta, used_sum

    def _phase2_strict_chains(self, remaining_tubes, raw_length, plan_id):
        plans = []
        # 转换为 length_counts + tube_meta_pool
        length_counts = {}
        tube_meta_pool = {}
        for t in remaining_tubes:
            length_counts[t['tube_length']] = length_counts.get(t['tube_length'], 0) + 1
            tube_meta_pool.setdefault(t['tube_length'], []).append(t)

        preferred = set()
        guard = 0
        while sum(length_counts.values()) > 0 and guard < 1000:
            guard += 1
            # 检查是否仅剩单一型号
            non_zero = [L for L, c in length_counts.items() if c > 0]
            if len(non_zero) <= 1:
                break  # 留给阶段三

            chain_plans, plan_id = self._build_chain(
                length_counts, tube_meta_pool, raw_length, plan_id, preferred
            )
            if chain_plans is None:
                # 任何起点都失败 -> 退化为常规切割（兜底，可能产生违规）
                fallback_used, fallback_sum = self._greedy_fill(
                    raw_length, length_counts, tube_meta_pool, prefer="desc"
                )
                if not fallback_used:
                    break
                leftover = raw_length - fallback_sum
                p = self._make_plan(plan_id, raw_length, fallback_used, None, leftover)
                p['perfect_source'] = "phase2_fallback"
                plans.append(p)
                plan_id += 1
                continue
            if not chain_plans:
                break  # 无可行起点 -> 进入阶段三或单独处理
            plans.extend(chain_plans)

        # 把剩余 tube_meta_pool 还原到 remaining_tubes
        new_remaining = []
        for L, lst in tube_meta_pool.items():
            new_remaining.extend(lst)
        return plans, new_remaining, plan_id

    def _phase3_host_provider(self, remaining_tubes, raw_length, plan_id):
        if not remaining_tubes:
            return [], remaining_tubes, plan_id
        algo = HostProviderAlgorithm()
        plans, remain, _, plan_id = algo.generate(
            remaining_tubes=remaining_tubes,
            raw_length=raw_length,
            start_plan_id=plan_id,
            leftovers=[],
            max_plans=None
        )
        return plans, remain, plan_id

    def _phase3_single_spec_finish(self, prior_plans, remaining_tubes, raw_length, plan_id):
        """阶段三单规格：plain / host 择优收尾，须在整体方案上满足硬约束。"""
        if not remaining_tubes:
            return None, plan_id
        finish_plans, remain, _, new_id = self._resolve_single_spec_finish(
            prior_plans,
            copy.deepcopy(remaining_tubes),
            [],
            raw_length,
            plan_id,
        )
        if not finish_plans or remain:
            return None, plan_id
        remaining_tubes.clear()
        return finish_plans, new_id

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        leftovers = leftovers if leftovers is not None else []
        plan_id = start_plan_id
        all_plans = []

        # 阶段一：完美切割（贪心 DFS 找余料 <= 阈值的组合）
        p1_plans, remaining_tubes, plan_id = self._phase1_perfect_cuts(remaining_tubes, raw_length, plan_id)
        all_plans.extend(p1_plans)

        p15_plans, remaining_tubes, plan_id = self._phase15_dual_splice_then_host(
            remaining_tubes, raw_length, plan_id)
        if p15_plans:
            all_plans.extend(p15_plans)
            is_ok, _viol = validate_strict_constraint(all_plans, raw_length)
            if not is_ok:
                all_plans, plan_id = self._finalize_tail_with_multi_algo(
                    all_plans, raw_length, plan_id)

        # 阶段二：复用现有合法性较好的算法做基线，并对违规链做局部重排修复
        p2_plans, remaining_tubes, plan_id = self._phase2_via_legacy_with_repair(remaining_tubes, raw_length, plan_id)
        all_plans.extend(p2_plans)

        # 阶段三：仅一种型号且数量足够时触发宿主-供给
        non_zero_lengths = {}
        for t in remaining_tubes:
            non_zero_lengths[t['tube_length']] = non_zero_lengths.get(t['tube_length'], 0) + 1
        p3_plans = []
        if remaining_tubes and len(non_zero_lengths) == 1:
            finish_p3, plan_id = self._phase3_single_spec_finish(
                all_plans, remaining_tubes, raw_length, plan_id)
            if finish_p3 is not None:
                p3_plans = finish_p3
                all_plans.extend(p3_plans)
            else:
                p3_plans, remaining_tubes, plan_id = self._phase3_host_provider(
                    remaining_tubes, raw_length, plan_id)
                all_plans.extend(p3_plans)

        # 兜底：仍有遗留则常规切割
        guard = 0
        while remaining_tubes and guard < 200:
            guard += 1
            length_counts = {}
            tube_meta_pool = {}
            for t in remaining_tubes:
                length_counts[t['tube_length']] = length_counts.get(t['tube_length'], 0) + 1
                tube_meta_pool.setdefault(t['tube_length'], []).append(t)
            used, used_sum = self._greedy_fill(raw_length, length_counts, tube_meta_pool, prefer="desc")
            if not used:
                break
            leftover = raw_length - used_sum
            p = self._make_plan(plan_id, raw_length, used, None, leftover)
            p['perfect_source'] = "phase_fallback"
            all_plans.append(p)
            plan_id += 1
            new_remaining = []
            for L, lst in tube_meta_pool.items():
                new_remaining.extend(lst)
            remaining_tubes = new_remaining

        # 段借出修复（4 段化重切的通用化形式）：对所有阶段产生的方案统一操作
        # 允许从阶段一完美切割方案里"借"出小段填补阶段二的孤岛违规（可由 ENABLE_SEGMENT_BORROW_REPAIR 关闭）
        if ENABLE_SEGMENT_BORROW_REPAIR:
            all_plans = self._attempt_segment_borrow(all_plans, raw_length)

        # 统计
        splice_count = sum(1 for p in all_plans for t in p['tubes'] if 'spliced_from' in t)
        perfect_cuts = sum(
            p.get('raw_materials', 1)
            for p in all_plans
            if is_no_splice_perfect_cut(p, raw_length)
        )
        total_waste = sum_unused_leftover(all_plans)

        self.last_run_stats = {
            "phase1_raw": len(p1_plans),
            "phase15_raw": len(p15_plans),
            "phase2_raw": len(p2_plans),
            "phase3_raw": len(p3_plans),
            "perfect_cuts": perfect_cuts,
            "splice_count": splice_count,
            "total_waste": total_waste
        }
        tw_hint = all_plans[0].get('tube_width') if all_plans else "-"
        logging.info(
            "三阶段算法 [宽度=%s] - 阶段一: %s 根, 阶段1.5: %s 根, 阶段二: %s 根, 阶段三: %s 根, "
            "本宽度无拼接完美切割: %s 根, 拼接次数: %s, 总余料: %s",
            tw_hint,
            len(p1_plans), len(p15_plans), len(p2_plans), len(p3_plans),
            perfect_cuts, splice_count, total_waste
        )
        all_plans = ensure_forward_splice_links(all_plans, raw_length)
        return all_plans, remaining_tubes, leftovers, plan_id


def length_counts_after(used_meta, length_counts):
    """辅助：返回扣除 used_meta 后的 length_counts 副本（用于尝试性合法性检查）。"""
    snapshot = dict(length_counts)
    for u in used_meta:
        snapshot[u['tube_length']] = snapshot.get(u['tube_length'], 0) - 1
    return snapshot


def count_chain_splice_segments(plans):
    """链式续接拼接段数量（不含宿主-供给结构化拼接，图面更易辨识）。"""
    return sum(
        1 for p in plans for t in p.get('tubes', [])
        if 'spliced_from' in t and t.get('host_role') not in ('host', 'provider')
    )


def validate_strict_constraint(plans, raw_length):
    """
    硬约束校验：每个方管宽度组内，除该组最后一根原材外，
    其它原材余料必须 <= SPLICE_THRESHOLD 或被本组另一方案精确消费。
    精确消费判定：方案 P 的 splice_info.to_plan 指向 Q，且 Q 内有 spliced_from == P.remaining_length。
    返回 (是否合法, 违规列表[(plan_id, leftover, reason)])。
    """
    if not plans:
        return True, []

    by_width = {}
    for p in plans:
        by_width.setdefault(p.get('tube_width'), []).append(p)

    violations = []
    for _, group in by_width.items():
        sorted_group = sorted(group, key=lambda x: x.get('plan_id', 0))
        if not sorted_group:
            continue
        last_id = sorted_group[-1].get('plan_id')
        plan_by_id = {p.get('plan_id'): p for p in sorted_group}

        for p in sorted_group:
            if p.get('plan_id') == last_id:
                continue
            leftover = p.get('remaining_length', 0)
            if leftover <= SPLICE_THRESHOLD:
                continue

            consumed = False
            to_plan = p.get('splice_info', {}).get('to_plan')
            if to_plan is not None and to_plan in plan_by_id:
                target = plan_by_id[to_plan]
                for t in target.get('tubes', []):
                    if t.get('spliced_from') == leftover:
                        consumed = True
                        break
                if not consumed and any(t.get('host_role') == 'provider' for t in target.get('tubes', [])):
                    consumed = True

            # 反向：上一根原材上的拼接段已声明消费本方案余料（四段链：原材 C 末段 ← 原材 D 尾 R0）
            if not consumed:
                prev_candidates = [
                    x for x in sorted_group
                    if x.get('plan_id', 0) < p.get('plan_id')
                ]
                if prev_candidates:
                    prev_p = prev_candidates[-1]
                    for t in prev_p.get('tubes', []):
                        if t.get('spliced_from') == leftover:
                            consumed = True
                            break

            if not consumed:
                violations.append((p.get('plan_id'), leftover, '孤岛余料：未被任何方案拼接'))

    return len(violations) == 0, violations


def validate_relaxed_constraint(plans, raw_length):
    """放宽校验：仅忽略「孤岛余料」(>阈值未消费)类违规，按用户原则将其视为可接受废料。
    仅供并联择优的最终评分使用；算法内部闸门仍用 validate_strict_constraint 严格把关，
    以保留阶段修复/回滚逻辑不被破坏。其它类型违规（当前不存在，预留）仍判违规。
    """
    is_ok, violations = validate_strict_constraint(plans, raw_length)
    if is_ok:
        return True, []
    kept = [v for v in violations if '孤岛余料' not in str(v[2])]
    return len(kept) == 0, kept


def print_plans_preview(plans, raw_length, project_name="-", logger=None):
    """绘制 DXF 前以参数化方式打印所有方案，便于人工核对。"""
    log_fn = logger.info if logger else print

    log_fn("================ 方案预览开始 ================")
    log_fn(f"项目: {project_name}")
    log_fn(f"原材长度: {raw_length}, 阈值: {SPLICE_THRESHOLD}")
    log_fn(f"方案数: {len(plans)}")
    log_fn(f"DXF合并后行数: {_count_dxf_merge_rows(plans)}, 唯一刀型: {_count_unique_cut_signatures(plans)}")

    grouped = {}
    for p in plans:
        grouped.setdefault(p.get('tube_width'), []).append(p)

    summaries = {}

    for width, gplans in grouped.items():
        log_fn(f"---- 方管宽度 {width} ({len(gplans)} 个方案) ----")
        sorted_gplans = sorted(gplans, key=lambda x: x.get('plan_id', 0))
        width_perfect = 0
        width_raw = 0
        width_splice = 0
        for p in sorted_gplans:
            tubes_desc = []
            row_tubes = p.get('tubes', [])
            sp_idx = [jj for jj, tt in enumerate(row_tubes) if 'spliced_from' in tt]
            first_sp = min(sp_idx) if sp_idx else None
            last_sp = max(sp_idx) if sp_idx else None
            # 捐赠段(provider)位置：拼接关系标注移至捐赠段
            prov_idx = [jj for jj, tt in enumerate(row_tubes) if tt.get('host_role') == 'provider']
            last_prov = max(prov_idx) if prov_idx else None
            for j, t in enumerate(row_tubes):
                if t.get('host_role') == 'provider':
                    label = format_tube_dim_label(
                        t,
                        use_full_splice_label=(last_prov is not None and j == last_prov),
                        segment_index=j,
                        first_sp_j=first_sp,
                        last_sp_j=last_sp,
                    )
                    tubes_desc.append(f"[供{label}]")
                elif 'spliced_from' in t:
                    # 接收段：host(宿主-供给)不标注拼接关系；链式续接维持原标注
                    label = format_tube_dim_label(
                        t,
                        use_full_splice_label=(last_sp is not None and j == last_sp and not (first_sp == last_sp == 0)),
                        segment_index=j,
                        first_sp_j=first_sp,
                        last_sp_j=last_sp,
                    )
                    tubes_desc.append(f"[拼{label}]")
                else:
                    tubes_desc.append(format_tube_dim_label(t))

            leftover = p.get('remaining_length', 0)
            tag_parts = []
            has_splice = any(
                ('spliced_from' in tt or tt.get('host_role') in ('provider', 'host'))
                for tt in p.get('tubes', [])
            )
            if is_no_splice_perfect_cut(p, raw_length):
                tag_parts.append("完美")
                pw = p.get('raw_materials', 1)
                width_perfect += pw
            if has_splice:
                tag_parts.append("拼接")
                width_splice += sum(1 for tt in p.get('tubes', []) if 'spliced_from' in tt)

            tag = ",".join(tag_parts) if tag_parts else "普通"
            raw_count = p.get('raw_materials', 1)
            width_raw += raw_count
            tail_parts = format_plan_tail_segments(p, sorted_gplans)
            line = (
                f"  方案#{p.get('plan_id')} [{tag}] x{raw_count}根 -> "
                f"{' + '.join(tubes_desc)}"
            )
            if tail_parts:
                line += ' | ' + ' | '.join(tail_parts)
            log_fn(line)

        summaries[width] = {
            'raw': width_raw,
            'perfect': width_perfect,
            'splice': width_splice,
            'merge_rows': _count_dxf_merge_rows(sorted_gplans),
        }

    # 预览校验与并联择优同口径：孤岛余料(>阈值未消费)按用户原则视为可接受废料，不算违规。
    is_valid, violations = validate_relaxed_constraint(plans, raw_length)
    total_merge_rows = _count_dxf_merge_rows(plans)
    log_fn("---- 全局统计（按宽度分列） ----")
    for tw in sorted(summaries.keys(), key=lambda x: (x is None, x), reverse=True):
        s = summaries[tw]
        log_fn(
            f"  宽度 {tw}: 原材 {s['raw']} 根, "
            f"无拼接完美 {s['perfect']} 根, 拼接段 {s['splice']}, "
            f"图面行数 {s['merge_rows']}"
        )
    log_fn(f"  总行数: {total_merge_rows}（DXF合并后）")
    log_fn(f"硬约束（全项目）: {'通过' if is_valid else '违规 ' + str(violations)}")
    log_fn("================ 方案预览结束 ================")


class BestFitAlgorithm(CuttingAlgorithmBase):
    """
    基础替代算法：Best-Fit（不做拼接，仅用于并联对比与后续扩展示例）。
    """

    name = "best_fit"

    def generate(self, remaining_tubes, raw_length, start_plan_id=1, leftovers=None, max_plans=None):
        cutting_plans = []
        plan_id = start_plan_id
        generated_count = 0
        leftovers = leftovers if leftovers is not None else []

        # 每轮选择一根原材：在当前余量下优先放入“最接近余量”的方管
        while remaining_tubes and (max_plans is None or generated_count < max_plans):
            current_raw = []
            remaining_length = raw_length

            while remaining_tubes:
                best_index = None
                best_gap = None
                for i, tube in enumerate(remaining_tubes):
                    gap = remaining_length - tube['tube_length']
                    if gap < 0:
                        continue
                    if best_gap is None or gap < best_gap:
                        best_gap = gap
                        best_index = i
                if best_index is None:
                    break
                tube = remaining_tubes.pop(best_index)
                current_raw.append(tube)
                remaining_length -= tube['tube_length']
                if remaining_length <= SPLICE_THRESHOLD:
                    break

            if not current_raw:
                break

            cutting_plans.append({
                'plan_id': plan_id,
                'tube_width': current_raw[0]['tube_width'],
                'raw_length': raw_length,
                'remaining_length': remaining_length,
                'tubes': current_raw,
                'pieces': len(current_raw),
                'raw_materials': 1,
                'splice': False,
                'splice_info': {'from_plan': None, 'to_plan': None, 'length': 0}
            })
            plan_id += 1
            generated_count += 1

        return cutting_plans, remaining_tubes, leftovers, plan_id

class TubeLayoutGenerator:
    def __init__(self):
        self.raw_length = 12000
        self.algorithms = {
            StrictPhasedAlgorithm.name: StrictPhasedAlgorithm(),
            UniformFourBarChainAlgorithm.name: UniformFourBarChainAlgorithm(),
            NormalDeepThenGreedyAlgorithm.name: NormalDeepThenGreedyAlgorithm(),
            GreedyThenDeepAlgorithm.name: GreedyThenDeepAlgorithm(),
            DeepThenGreedyAlgorithm.name: DeepThenGreedyAlgorithm(),
            HostProviderAlgorithm.name: HostProviderAlgorithm(),
            MixedDonorHostProviderAlgorithm.name: MixedDonorHostProviderAlgorithm(),
            UniformHubGraphAlgorithm.name: UniformHubGraphAlgorithm(),
            BestFitAlgorithm.name: BestFitAlgorithm(),
        }
    
    def generate_tube_layout(
            self,
            project_name,
            parameter_tables,
            strategy_config=None,
            skip_plans_preview: bool = False):
        """
        生成方管排布图
        :param project_name: 项目名称
        :param parameter_tables: 参数表列表
        :param strategy_config: 可选，覆盖默认并联算法列表（见 _get_default_strategy_config）
        :param skip_plans_preview: True 时跳过生成 DXF 前的逐方案 INFO 预览（大项目可明显减日志与少量 CPU）
        :return: (BytesIO, filename) 内存流和文件名
        """
        try:
            logging.info(f"开始生成方管排布图，项目名称: {project_name}")
            
            # 1. 处理所有参数表数据
            tube_data = self.process_frontend_data(parameter_tables)
            
            # 如果没有有效的方管数据，报错
            if not tube_data:
                alarm_logging.error("没有有效的方管数据")
                raise ValueError("没有有效的方管数据")
            
            # 2. 按方管宽度分组
            grouped_tubes = self.group_by_tube_width(tube_data)
            logging.info(f"按方管宽度分组完成，分组数量: {len(grouped_tubes)}")
            
            # 3. 对每个宽度组生成切割方案
            all_cutting_plans = []
            for width, tubes in grouped_tubes.items():
                cutting_plan = self.generate_cutting_plan(tubes, strategy_config=strategy_config)
                all_cutting_plans.extend(cutting_plan)
                      
            # 4. 直接生成DXF文件到内存
            return self.convert_to_dxf(
                all_cutting_plans, project_name, skip_plans_preview=skip_plans_preview)
        except Exception as e:
            alarm_logging.error(f"生成方管排布图时出错: {e}")
            # 当数据无法读取时，报错，不要使用测试函数
            raise
    
    def process_frontend_data(self, parameter_tables):
        """
        处理前端数据
        :param parameter_tables: 参数表列表
        :return: 处理后的数据列表
        """
        tube_data = []
        
        logging.info(f"开始处理前端数据，参数表数量: {len(parameter_tables)}")
        
        for i, table in enumerate(parameter_tables):
            # 获取方管宽度
            tube_width = 0
            parameters = table.get('parameters', {})
            if parameters:
                # 处理 JSON 文件中的数据结构
                tube_width = parameters.get('方管宽度(mm)', 0)
            else:
                # 处理前端传递的数据结构
                tube_width = table.get('tubeWidth', 0)
            try:
                tube_width = int(tube_width)
            except (ValueError, TypeError) as e:
                alarm_logging.error(f"转换方管宽度时出错: {e}")
                continue
            if tube_width <= 0:
                alarm_logging.warning(f"方管宽度无效: {tube_width}")
                continue
            
            # 获取屈服承载力
            yield_force = 0
            if 'design_force' in table:
                # 处理 JSON 文件中的数据结构
                yield_force = table.get('design_force', 0)
            else:
                # 处理前端传递的数据结构
                yield_force = table.get('designForce', 0)
            try:
                yield_force = int(yield_force)
            except (ValueError, TypeError) as e:
                alarm_logging.error(f"转换屈服承载力时出错: {e}")
                yield_force = 0
            
            # 处理长度-数量对应表
            length_quantity_table = []
            if 'length_quantity' in table:
                # 处理 JSON 文件中的数据结构
                length_quantity_table = table.get('length_quantity', [])
            else:
                # 处理前端传递的数据结构
                length_quantity_table = table.get('lengthQuantityTable', [])
            if not isinstance(length_quantity_table, list):
                alarm_logging.warning("长度-数量对应表不是列表类型")
                continue
            
            for j, item in enumerate(length_quantity_table):
                length = 0
                quantity = 0
                if isinstance(item, list) and len(item) >= 2:
                    # 处理 JSON 文件中的数据结构
                    length = item[0]
                    quantity = item[1]
                elif isinstance(item, dict):
                    # 处理前端传递的数据结构
                    length = item.get('length', 0)
                    quantity = item.get('quantity', 0)
                else:
                    alarm_logging.warning("长度-数量项不是列表类型或字典类型")
                    continue
                
                try:
                    length = int(length)
                    quantity = int(quantity)
                except (ValueError, TypeError) as e:
                    alarm_logging.error(f"转换长度或数量时出错: {e}")
                    continue
                
                if length > 0 and quantity > 0:
                    # 方管长度 = 产品长度 - 300
                    tube_length = length - 300
                    if tube_length > 0:
                        tube_data.append({
                            'tube_width': tube_width,
                            'tube_length': tube_length,
                            'quantity': quantity,
                            'yield_force': yield_force,
                            'product_length': length
                        })
        
        logging.info(f"处理完成，生成的方管数据数量: {len(tube_data)}")
        return tube_data
    
    def group_by_tube_width(self, tube_data):
        """
        按方管宽度分组
        :param tube_data: 处理后的数据列表
        :return: 按方管宽度分组的数据
        """
        grouped = {}
        
        for item in tube_data:
            width = item['tube_width']
            if width not in grouped:
                grouped[width] = []
            grouped[width].append(item)
        
        return grouped
    
    def _build_remaining_tubes(self, tubes):
        sorted_tubes = sorted(tubes, key=lambda x: x['tube_length'], reverse=True)
        remaining_tubes = []
        for tube in sorted_tubes:
            for _ in range(tube['quantity']):
                remaining_tubes.append({
                    'tube_length': tube['tube_length'],
                    'product_length': tube['product_length'],
                    'yield_force': tube['yield_force'],
                    'tube_width': tube['tube_width']
                })
        return remaining_tubes

    def _evaluate_cutting_plans(self, cutting_plans):
        """
        评分元组（值越小越优，按字典序）：
        1) 总余料（各方案未再使用的 remaining_length 之和，与图面「余料总和」一致）
        2) 拼接次数
        3) 原材使用根数
        """
        if not cutting_plans:
            return (float('inf'), float('inf'), float('inf'))

        total_waste = sum_scoring_waste(cutting_plans)
        splice_count = sum(1 for p in cutting_plans for t in p.get('tubes', []) if 'spliced_from' in t)
        raw_materials = sum(p.get('raw_materials', 1) for p in cutting_plans)
        return (total_waste, splice_count, raw_materials)

    def _get_default_strategy_config(self):
        return {
            "mode": "parallel",
            "parallel_algorithms": [
                StrictPhasedAlgorithm.name,
                UniformFourBarChainAlgorithm.name,
                NormalDeepThenGreedyAlgorithm.name,
                GreedyThenDeepAlgorithm.name,
                DeepThenGreedyAlgorithm.name,
                HostProviderAlgorithm.name,
                MixedDonorHostProviderAlgorithm.name,
                UniformHubGraphAlgorithm.name
            ],
            "serial_stages": [AlgorithmStage(name=StrictPhasedAlgorithm.name)]
        }

    def _get_fast_strategy_config(self):
        """
        快速模式：每个宽度组只跑 strict_phased（最终选用并联结果时的基准算法），
        省去与其它算法的并联竞选，通常可缩短大半 CPU 时间；代价是不再横向对比其它贪心策略。
        """
        return {
            "mode": "parallel",
            "parallel_algorithms": [StrictPhasedAlgorithm.name],
            "serial_stages": [AlgorithmStage(name=StrictPhasedAlgorithm.name)]
        }

    def _normalize_serial_stages(self, serial_stages):
        normalized = []
        for stage in serial_stages:
            if isinstance(stage, AlgorithmStage):
                normalized.append(stage)
            elif isinstance(stage, dict):
                normalized.append(AlgorithmStage(
                    name=stage.get("name"),
                    max_plans=stage.get("max_plans")
                ))
        return [s for s in normalized if s.name]

    def _count_no_splice_perfect(self, plans):
        return sum(
            p.get('raw_materials', 1)
            for p in plans
            if is_no_splice_perfect_cut(p, self.raw_length)
        )

    def _detect_problem_chain_ids(self, plans):
        """
        识别“问题链”：含拼接关系且其中某段拼接料 <= SPLICE_THRESHOLD 的链。
        返回 plan_id 集合。
        """
        problem_ids = set()
        for p in plans:
            tubes = p.get('tubes', [])
            for t in tubes:
                # 拼接接口段的“新增段”长度即 t['tube_length']（spliced_from 是来自上一根的尾料）
                if 'spliced_from' in t and t.get('tube_length', 0) <= SPLICE_THRESHOLD:
                    problem_ids.add(p.get('plan_id'))
                    break
        return problem_ids

    def _repair_problem_chains(self, plans, tubes):
        """
        步骤一：扫描问题链，并尝试用全部剩余/同宽度池跨型号重排修复。
        - 重排范围限定为本组内同宽度
        - 修复后按现有择优规则比较
        - 不优则保留原方案
        """
        problem_ids = self._detect_problem_chain_ids(plans)
        if not problem_ids:
            return plans

        # 简化策略：把所有问题链涉及方案剥离，对应方管需求重新进入待处理池，
        # 然后用 GreedyThenDeepAlgorithm 在剩余方管池上重新生成方案。
        remaining_unused = [p for p in plans if p.get('plan_id') not in problem_ids]
        problem_plans = [p for p in plans if p.get('plan_id') in problem_ids]
        # 收集问题链消耗的产品需求
        recovered_tubes = []
        for p in problem_plans:
            for t in p.get('tubes', []):
                if t.get('host_role') == 'provider':
                    continue  # provider 不还原为需求
                tl = t.get('original_length') if 'spliced_from' in t else t.get('tube_length')
                if tl is None:
                    continue
                recovered_tubes.append({
                    'tube_length': tl,
                    'product_length': t.get('product_length'),
                    'yield_force': t.get('yield_force'),
                    'tube_width': t.get('tube_width')
                })

        if not recovered_tubes:
            return plans

        # 重排
        algo = self.algorithms.get(GreedyThenDeepAlgorithm.name)
        if algo is None:
            return plans

        max_existing_id = max((p.get('plan_id', 0) for p in remaining_unused), default=0)
        repaired, remain_after, _, _ = algo.generate(
            remaining_tubes=recovered_tubes,
            raw_length=self.raw_length,
            start_plan_id=max_existing_id + 1,
            leftovers=[],
            max_plans=None
        )
        if remain_after:
            return plans  # 修复未能完全覆盖时直接放弃

        new_plans = remaining_unused + repaired
        # 比较修复前后按既定规则
        old_perfect = self._count_no_splice_perfect(plans)
        new_perfect = self._count_no_splice_perfect(new_plans)
        old_score = self._evaluate_cutting_plans(plans)
        new_score = self._evaluate_cutting_plans(new_plans)
        if (new_perfect > old_perfect) or (new_perfect == old_perfect and new_score < old_score):
            logging.info(
                "问题链修复生效：完美切割 %s -> %s, 评分 %s -> %s",
                old_perfect, new_perfect, old_score, new_score
            )
            return new_plans
        return plans

    def _run_parallel_algorithms(self, tubes, algorithm_names):
        """
        择优规则（升序字典序，越前越优）：
        1) 违规数（合法>违规）
        2) 原材根数（最少用料，硬指标）
        3) 无拼接完美原材数（越多越好，取负号参与排序）
        4) 总余料（未再使用的余料总和）
        5) 拼接总数（含宿主-供给，越少越好）
        6) DXF 合并后图面行数（越少越好，质量并列时压短图幅）
        7) 唯一刀型数

        原材数优先于完美数/余料/拼接：杜绝「为多完美管/省余料而多用料」。
        拼接用总数（含宿主供给），避免宿主供给拼接被隐藏而压过更优用料方案。

        另：合法解在「完美数差≤1、拼接差≤2、余料不更差、原材相同」时，
        若合并行至少少 5 行，则优先更短图面。
        """
        best_plans = []
        best_algo_name = None
        best_key = None
        candidates = []

        for algo_name in algorithm_names:
            algorithm = self.algorithms.get(algo_name)
            if algorithm is None:
                alarm_logging.warning(f"并联算法不存在，已跳过: {algo_name}")
                continue

            remaining_tubes = self._build_remaining_tubes(tubes)
            plans, remain, _, _ = algorithm.generate(
                remaining_tubes=remaining_tubes,
                raw_length=self.raw_length,
                start_plan_id=1,
                leftovers=[],
                max_plans=None
            )
            if remain:
                alarm_logging.warning(f"算法 {algo_name} 未覆盖全部方管，剩余数量: {len(remain)}，使用兜底算法补齐")
                fb = self.algorithms.get(GreedyThenDeepAlgorithm.name)
                if fb is not None:
                    max_id = max((p.get('plan_id', 0) for p in plans), default=0)
                    extra, _, _, _ = fb.generate(
                        remaining_tubes=remain,
                        raw_length=self.raw_length,
                        start_plan_id=max_id + 1,
                        leftovers=[],
                        max_plans=None
                    )
                    plans.extend(extra)

            # 并联择优用「放宽校验」：孤岛余料(>阈值未消费)按用户原则视为可接受废料，
            # 不再硬性否决；由原材数/余料/软偏好决定取舍。算法内部仍用严格校验把关。
            is_valid, violations = validate_relaxed_constraint(plans, self.raw_length)
            score = self._evaluate_cutting_plans(plans)
            perfect_count = self._count_no_splice_perfect(plans)
            scoring_waste, splice_count, raw_count = score
            accounting_waste = sum_unused_leftover(plans)
            chain_splice = count_chain_splice_segments(plans)
            merge_rows = _count_dxf_merge_rows(plans)
            unique_cuts = _count_unique_cut_signatures(plans)
            # 择优顺序：原材数是硬指标，优先于余料；杜绝「为省余料而多拼/多用料」。
            # 余料仍参与比较，但同原材前提下才比余料；图面行数靠软偏好另行放宽。
            # 拼接用总数（含宿主供给），避免宿主供给拼接被隐藏而压过更优用料方案。
            sort_key = (
                len(violations),
                raw_count,
                -perfect_count,
                scoring_waste,
                splice_count,
                merge_rows,
                unique_cuts,
            )
            candidates.append({
                'name': algo_name,
                'plans': plans,
                'key': sort_key,
                'perfect': perfect_count,
                'splice': splice_count,
                'chain': chain_splice,
                'waste': scoring_waste,
                'raw': raw_count,
                'merge': merge_rows,
            })

            logging.info(
                "并联算法结果 %s - 合法: %s, 违规数: %s, 择优余料: %s, 账面余料: %s, 拼接: %s, 链式拼接: %s, 原材: %s, "
                "本宽度无拼接完美: %s, 合并行: %s, 唯一刀型: %s, 评分键: %s",
                algo_name, is_valid, len(violations),
                scoring_waste, accounting_waste, splice_count, chain_splice, raw_count,
                perfect_count, merge_rows, unique_cuts, sort_key
            )
            if best_key is None or sort_key < best_key:
                best_key = sort_key
                best_algo_name = algo_name
                best_plans = plans

        # 质量基本持平时，用更短图面替换。
        # 按用户原则：原材数是硬指标；同原材前提下，允许余料「适当」增多以换取更少图面行数/拼接，
        # 因为高于阈值的余料可作废料，不必为压低余料而强行拼接（强行拼接往往反而多用料）。
        # 余料容忍度取原材长度的 1/4（适度让步），图面行数至少少 2 行才换。
        if best_key is not None and best_key[0] == 0 and best_algo_name:
            waste_tolerance = max(self.raw_length // 4, 1000)
            base = next(c for c in candidates if c['name'] == best_algo_name)
            for c in candidates:
                if c['key'][0] != 0:
                    continue
                if c['raw'] != base['raw']:
                    continue
                if c['waste'] > base['waste'] + waste_tolerance:
                    continue
                if c['perfect'] < base['perfect'] - 1:
                    continue
                if c['splice'] > base['splice'] + 2:
                    continue
                if c['merge'] <= base['merge'] - 2 and c['name'] != best_algo_name:
                    logging.info(
                        "并联软偏好更短图面: %s -> %s (合并行 %s -> %s, 完美 %s->%s, 拼接 %s->%s, 余料 %s->%s)",
                        best_algo_name, c['name'],
                        base['merge'], c['merge'],
                        base['perfect'], c['perfect'],
                        base['splice'], c['splice'],
                        base['waste'], c['waste'],
                    )
                    best_algo_name = c['name']
                    best_plans = c['plans']
                    best_key = c['key']
                    base = c

        logging.info(
            "并联算法最终选择: %s (评分键: %s)",
            best_algo_name, best_key
        )
        return best_plans

    def _run_serial_algorithms(self, tubes, serial_stages):
        remaining_tubes = self._build_remaining_tubes(tubes)
        leftovers = []
        all_plans = []
        next_plan_id = 1

        for stage in serial_stages:
            algorithm = self.algorithms.get(stage.name)
            if algorithm is None:
                alarm_logging.warning(f"串联阶段算法不存在，已跳过: {stage.name}")
                continue

            plans, remaining_tubes, leftovers, next_plan_id = algorithm.generate(
                remaining_tubes=remaining_tubes,
                raw_length=self.raw_length,
                start_plan_id=next_plan_id,
                leftovers=leftovers,
                max_plans=stage.max_plans
            )
            logging.info(f"串联算法阶段完成: {stage.name}, 生成方案数: {len(plans)}, 剩余方管数: {len(remaining_tubes)}")
            all_plans.extend(plans)

            if not remaining_tubes:
                break

        # 串联阶段未完全覆盖时，回退到默认算法补齐
        if remaining_tubes:
            fallback_algo = self.algorithms[GreedyThenDeepAlgorithm.name]
            plans, remaining_tubes, leftovers, next_plan_id = fallback_algo.generate(
                remaining_tubes=remaining_tubes,
                raw_length=self.raw_length,
                start_plan_id=next_plan_id,
                leftovers=leftovers,
                max_plans=None
            )
            all_plans.extend(plans)
            if remaining_tubes:
                alarm_logging.warning(f"串联模式补齐后仍有未处理方管: {len(remaining_tubes)}")

        return all_plans

    def generate_cutting_plan(self, tubes, strategy_config=None):
        """
        生成切割方案（支持并联/串联框架）
        :param tubes: 同一宽度的方管列表
        :param strategy_config: 算法策略配置
        :return: 切割方案
        """
        config = copy.deepcopy(strategy_config) if strategy_config else self._get_default_strategy_config()
        mode = config.get("mode", "parallel")

        if mode == "serial":
            serial_stages = self._normalize_serial_stages(
                config.get("serial_stages", self._get_default_strategy_config()["serial_stages"])
            )
            if not serial_stages:
                serial_stages = [AlgorithmStage(name=GreedyThenDeepAlgorithm.name)]
            plans = self._run_serial_algorithms(tubes, serial_stages)
            plans = repair_orphan_islands_by_trim(plans, self.raw_length)
            expected_qty = sum(t.get('quantity', 0) for t in tubes)
            delivered_qty = count_delivered_products(plans)
            if delivered_qty != expected_qty:
                alarm_logging.warning(
                    "切割方案产品根数与输入库存不一致：输入 %s 根，方案统计 %s 根",
                    expected_qty, delivered_qty,
                )
            return plans

        algorithm_names = config.get("parallel_algorithms", self._get_default_strategy_config()["parallel_algorithms"])
        if not algorithm_names:
            algorithm_names = [GreedyThenDeepAlgorithm.name]
        plans = self._run_parallel_algorithms(tubes, algorithm_names)
        plans = ensure_forward_splice_links(plans, self.raw_length)
        plans = repair_orphan_islands_by_trim(plans, self.raw_length)
        expected_qty = sum(t.get('quantity', 0) for t in tubes)
        delivered_qty = count_delivered_products(plans)
        if delivered_qty != expected_qty:
            alarm_logging.warning(
                "切割方案产品根数与输入库存不一致：输入 %s 根，方案统计 %s 根",
                expected_qty, delivered_qty,
            )
        return plans
    

    
    def convert_to_dxf(self, cutting_plans, project_name, skip_plans_preview: bool = False):
        """
        将切割方案转换为DXF文件
        :param cutting_plans: 切割方案列表
        :param project_name: 项目名称
        :param skip_plans_preview: 为 True 时不调用 print_plans_preview
        :return: (BytesIO, filename) 内存流和文件名
        """
        try:
            # 图面/预览统一：实体切段按长度从长到短排序（拼接相关段保持原位，质量不变）
            for _p in cutting_plans:
                _sort_solid_segments_desc_for_display(_p)

            # 在 DXF 生成前打印参数化方案预览（含硬约束校验）
            if not skip_plans_preview:
                try:
                    print_plans_preview(cutting_plans, self.raw_length, project_name=project_name, logger=logging)
                except Exception as preview_err:
                    alarm_logging.warning(f"方案预览打印失败: {preview_err}")

            project_name = str(project_name) if project_name else 'unnamed'
            # 移除可能导致路径问题的字符，允许中文字符
            import re
            safe_project_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_-]', '', project_name)
            safe_project_name = safe_project_name[:20]  # 限制长度
            # 确保safe_project_name不为空
            safe_project_name = safe_project_name if safe_project_name else 'unnamed'
            
            # 使用项目名作为文件名
            filename = f'{safe_project_name}_方管排布图.dxf'
            
            # 分宽度按切割形态合并（相同刀型合并 raw_materials，图面显示「×N根」）
            merged_plans = []
            grouped_by_width = {}
            for plan in cutting_plans:
                grouped_by_width.setdefault(plan.get('tube_width'), []).append(copy.deepcopy(plan))

            for _, width_plans in grouped_by_width.items():
                merged_plans.extend(_merge_plans_for_dxf(width_plans))

            # 绘制顺序由 generate_dxf_directly 内部统一排序（按宽度降序 + 纯完美优先 + min_plan_id），
            # 此处不再重复排序，避免双重计算被覆盖。
            return self.generate_dxf_directly(
                project_name, merged_plans, filename, stats_plans=cutting_plans,
            )
        except Exception as e:
            logging.error(f"转换为DXF文件时出错: {e}")
            raise
    
    def generate_dxf_directly(self, project_name, cutting_plans, filename, stats_plans=None):
        """
        直接生成DXF文件到内存
        :param project_name: 项目名称
        :param cutting_plans: 图面绘制用方案（可为合并后）
        :param filename: 文件名
        :param stats_plans: 余料/下料总长统计用方案（须保留 splice_info；默认与 cutting_plans 相同）
        :return: (BytesIO, filename) 内存流和文件名
        """
        stats_plans = stats_plans if stats_plans is not None else cutting_plans
        try:
            import ezdxf
            import datetime
            from ezdxf.enums import TextEntityAlignment
            from io import BytesIO
            
            # 创建一个新的DXF文档
            doc = ezdxf.new("R2018")
            msp = doc.modelspace()
            
            # 添加默认图层（不需要创建图层'0'，因为DXF默认包含）
            doc.layers.new("TUBE", dxfattribs={"color": 3})  # 绿色
            doc.layers.new("TEXT", dxfattribs={"color": 3})  # 绿色
            doc.layers.new("DIMENSION", dxfattribs={"color": 3})  # 绿色
            
            # 添加标注样式
            doc.dimstyles.add(
                name="Standard",
                dxfattribs={
                    "dimtxt": 3.5,  # 标注文字高度
                    "dimclrd": 0,   # 标注线颜色（0表示随层）
                    "dimasz": 4.0,  # 箭头大小
                    "dimtad": 1,    # 文字在尺寸线上方居中
                    "dimjust": 0,   # 尺寸线中间对齐
                    "dimlwd": -2,   # 标注线宽（-2表示默认宽度）
                    "dimexo": 0.0,  # 尺寸线超出尺寸界限的长度
                    "dimscale": 30,  # 标注比例
                    "dimalt": 0,    # 不使用替代单位
                    "dimadec": 2,   # 小数位数
                    "dimdsep": 44   # 小数分隔符（44是逗号）
                }
            )
            
            # 按方管宽度分组切割方案（图面）与统计（余料须用未合并的 stats_plans）
            grouped_plans = {}
            tube_stats = {}
            total_unused_leftover = 0  # 不再使用的余料总和（全局）

            for plan in cutting_plans:
                tube_width = plan['tube_width']
                if tube_width not in grouped_plans:
                    grouped_plans[tube_width] = []
                grouped_plans[tube_width].append(plan)

            for plan in stats_plans:
                tube_width = plan['tube_width']
                if tube_width not in tube_stats:
                    tube_stats[tube_width] = {'count': 0, 'length': 0, 'raw_materials': 0, 'unused_leftover': 0}
                rm = plan.get('raw_materials', 1)
                tube_stats[tube_width]['count'] += (
                    len([t for t in plan['tubes'] if t.get('host_role') != 'provider'])
                    * rm
                )
                tube_stats[tube_width]['raw_materials'] += rm
                if not is_leftover_used_by_later_plan(plan, stats_plans):
                    plan_leftover = plan.get('remaining_length', 0) * rm
                    tube_stats[tube_width]['unused_leftover'] += plan_leftover
                    total_unused_leftover += plan_leftover
            
            # 绘制每个宽度组的排布图
            
            # 按宽度降序排序，先绘制宽度较大的方管
            sorted_widths = sorted(grouped_plans.keys(), reverse=True)
            for i, width in enumerate(sorted_widths):
                # 计算第n个宽度组的初始坐标
                # x为（n-1）*15000，y为0
                n = i + 1
                current_x = (n - 1) * 15000
                current_y = 0  # 初始y坐标
                plans = grouped_plans[width]
                
                # 计算当前宽度组的统计信息
                count = tube_stats[width]['count']
                length = sum_brb_tube_demand_length(stats_plans, tube_width=width)
                raw_materials = tube_stats[width]['raw_materials']
                raw_capacity = raw_materials * self.raw_length
                
                unused_leftover = tube_stats[width]['unused_leftover']
                combined_text = (
                    f"{project_name} BRB, {width}方管下料总长{length}，"
                    f"需{raw_materials}根12米方管(原材{raw_capacity})，余料总和：{unused_leftover}mm"
                )
                msp.add_text(
                    combined_text,
                    dxfattribs={
                        "layer": "TEXT",
                        "width": 0.8,
                        "height": 200,
                        "insert": (current_x, current_y)
                    }
                )
                current_y -= 650  # 行间距
                
                raw_len_bar = self.raw_length
                
                # 不再覆盖方案余料：绘制与统计必须以算法给出的 remaining_length 为准，
                # 否则会把「余料段」错误摊进切段总长，图面显示成虚假「满分填满」的完美切割。
                for plan in plans:
                    ref_plan = _resolve_stats_plan_for_dxf(plan, stats_plans)
                    used_sum = sum(tube['tube_length'] for tube in plan['tubes'])
                    stored_lo = plan.get('remaining_length', 0)
                    carry_out = get_outbound_splice_carry(ref_plan, stats_plans)
                    if stored_lo is None:
                        plan['remaining_length'] = raw_len_bar - used_sum
                    elif used_sum + stored_lo + carry_out != raw_len_bar:
                        alarm_logging.warning(
                            "DXF 绘制：方案 #%s 长度不闭合（切段 %s + 余料 %s + 续接 %s ≠ 原材 %s），仍以算法数据绘制",
                            plan.get('plan_id'), used_sum, stored_lo, carry_out, raw_len_bar,
                        )

                # 图面竖向排布：纯完美行优先（无拼接关系的行），拼接相关行按合并前最小 plan_id 分组聚拢，
                # 使宿主行与其供给行相邻，避免被无关刀型行隔开。
                sorted_plans = sorted(
                    plans,
                    key=lambda p: (
                        0 if not p.get('_dxf_is_splice_row', False) else 1,
                        p.get('_merge_min_plan_id', p.get('plan_id', 0)),
                    ),
                )
                
                # 绘制当前宽度组的切割方案
                for i, plan in enumerate(sorted_plans):
                    ref_plan = _resolve_stats_plan_for_dxf(plan, stats_plans)
                        
                    # 使用当前y坐标作为方管的垂直中心
                    y = current_y
                    
                    # 获取当前方管的高度（实际宽度值）
                    rect_height = int(plan['tube_width'])
                    
                    # 为每个切割方案创建局部x坐标变量，使用宽度组的初始x坐标
                    plan_x = current_x
                    # 保存切割方案的开始位置，用于计算根数标注的位置
                    plan_start_x = plan_x
                    # 在每个原材的开始部分添加宽度标注（每个原材只标注一次）
                    rect_height = int(plan['tube_width'])
                    rect_top = y + rect_height / 2
                    rect_bottom = y - rect_height / 2
                    # 标注的两个端点（方管的顶部和底部）
                    p1 = (plan_x + 10, rect_bottom)  # 底部点
                    p2 = (plan_x + 10, rect_top)  # 顶部点
                    # 标注的基准点位置
                    base = (plan_x - 10 - 100, y)  # 标注文本的位置
                    # 创建线性标注
                    dim = msp.add_linear_dim(
                        base=base,
                        p1=p1,
                        p2=p2,
                        text=str(plan['tube_width']),
                        dimstyle="Standard",
                        dxfattribs={
                            "layer": "DIMENSION",
                            "color": 3,  # 绿色
                            "lineweight": 25
                        },
                        angle=90  # 垂直标注
                    )
                    dim.render()
                    
                    # 只给第一根方管增加总长的线性标注
                    if i == 0:
                        # 线性标注的两个端点（方管的左右两端）
                        p1 = (plan_x, rect_top)  # 左端点（在方管上方）
                        p2 = (plan_x + raw_len_bar, rect_top)  # 右端点（在方管上方）
                        # 标注的基准点位置（方管上方中间）
                        base = (plan_x + raw_len_bar / 2, rect_top + 280)  # 标注文本的位置，在方管上方
                        # 创建线性标注
                        dim = msp.add_linear_dim(
                            base=base,
                            p1=p1,
                            p2=p2,
                            text=str(raw_len_bar),
                            dimstyle="Standard",
                            dxfattribs={
                                "layer": "DIMENSION",
                                "color": 3,  # 绿色
                                "lineweight": 25
                            },
                            angle=0  # 水平标注
                        )
                        dim.render()

                    tubes_row = plan['tubes']

                    def _is_splice_seg(t):
                        if 'spliced_from' in t:
                            return True
                        if t.get('host_role') == 'provider':
                            return True
                        if t.get('host_role') == 'host' and 'spliced_from' in t:
                            return True
                        return False

                    splice_positions = [jj for jj, t in enumerate(tubes_row) if _is_splice_seg(t)]
                    last_sp_j = max(splice_positions) if splice_positions else None
                    first_sp_j = min(splice_positions) if splice_positions else None
                    # 捐赠段(provider)的最后一个位置：拼接关系标注移至捐赠段，不受 j==0 抑制
                    provider_positions = [jj for jj, t in enumerate(tubes_row) if t.get('host_role') == 'provider']
                    last_provider_j = max(provider_positions) if provider_positions else None

                    for j, tube in enumerate(tubes_row):
                        length = tube['tube_length']
                        product_length = tube['product_length']
                        
                        # 方管矩形的高度（使用实际的宽度值）
                        rect_height = int(plan['tube_width'])
                        rect_top = y + rect_height / 2
                        rect_bottom = y - rect_height / 2
                        
                        # 绘制方管矩形（使用四条线，白色粗实线）
                        # 上边
                        msp.add_line(
                            (plan_x, rect_top),
                            (plan_x + length, rect_top),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        # 下边
                        msp.add_line(
                            (plan_x, rect_bottom),
                            (plan_x + length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        
                        # 只绘制第一个方管段的左边
                        if j == 0:
                            msp.add_line(
                                (plan_x, rect_top),
                                (plan_x, rect_bottom),
                                dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                            )
                        
                        # 绘制右边（作为下一个方管段的左边）
                        msp.add_line(
                            (plan_x + length, rect_top),
                            (plan_x + length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        
                        # 拼接标注：全图规则——仅在本根原材的「最后一个拼接段」上标注拼接关系；
                        # 承接上一根余料的第一段（通常 j==0 且整根仅此一处拼接）只标本段实长，避免与上一根余料区重复。
                        # 捐赠段(provider)标注拼接关系（移至此处），不受 j==0 抑制；接收段(host)不再标注。
                        use_full_splice_label = False
                        if tube.get('host_role') == 'provider':
                            if last_provider_j is not None and j == last_provider_j:
                                use_full_splice_label = True
                        elif last_sp_j is not None and j == last_sp_j:
                            if not (first_sp_j == last_sp_j == 0):
                                use_full_splice_label = True
                        dim_text = format_tube_dim_label(
                            tube,
                            use_full_splice_label=use_full_splice_label,
                            segment_index=j,
                            first_sp_j=first_sp_j,
                            last_sp_j=last_sp_j,
                        )
                        
                        # 线性标注的两个端点（方管段的左右两端）
                        p1 = (plan_x, rect_top)  # 左端点
                        p2 = (plan_x + length, rect_top)  # 右端点
                        # 标注的基准点位置（方管段上方中间）
                        base = (plan_x + length / 2, y + rect_height / 2 + 100)  # 标注文本的位置，加高50
                        # 创建线性标注
                        dim = msp.add_linear_dim(
                            base=base,
                            p1=p1,
                            p2=p2,
                            text=dim_text,
                            dimstyle="Standard",
                            dxfattribs={
                                "layer": "DIMENSION",
                                "color": 3,  # 绿色
                                "lineweight": 25
                            },
                            angle=0  # 水平标注
                        )
                        dim.render()
                        
                        # 宽度标注已在原材开始部分添加，每个原材只标注一次
                        
                        # 在方管内部添加方管信息（格式：BRB-屈服力-产品长度）
                        tube_info = f"BRB-{tube['yield_force']}-{product_length}"
                        text_height = 120
                        tube_label = msp.add_text(
                            tube_info,
                            dxfattribs={
                                "layer": "TEXT",
                                "height": text_height,
                            },
                        )
                        tube_label.set_placement(
                            (plan_x + length / 2, y),
                            align=TextEntityAlignment.MIDDLE_CENTER,
                        )
                        
                        plan_x += length
                    
                    # 尾端续接段（整百拆分或整段前送，不计入 remaining_length）
                    carry_out = get_outbound_splice_carry(ref_plan, stats_plans)
                    if carry_out > 0:
                        rect_top = y + rect_height / 2
                        rect_bottom = y - rect_height / 2
                        msp.add_line(
                            (plan_x, rect_top), (plan_x + carry_out, rect_top),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7},
                        )
                        msp.add_line(
                            (plan_x, rect_bottom), (plan_x + carry_out, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7},
                        )
                        msp.add_line(
                            (plan_x, rect_top), (plan_x, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7},
                        )
                        msp.add_line(
                            (plan_x + carry_out, rect_top), (plan_x + carry_out, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7},
                        )
                        carry_tube = None
                        to_plan_id = (ref_plan.get('splice_info') or {}).get('to_plan')
                        for cp in stats_plans:
                            if cp.get('plan_id') != to_plan_id:
                                continue
                            if cp.get('tube_width') != plan.get('tube_width'):
                                continue
                            for ct in cp.get('tubes', []):
                                if ct.get('spliced_from') == carry_out:
                                    carry_tube = ct
                                    break
                            break
                        if carry_tube:
                            carry_text = (
                                f"{carry_out}（+{carry_tube['tube_length']}="
                                f"{carry_tube.get('original_length', carry_tube['tube_length'] + carry_out)}）"
                            )
                            carry_info = (
                                f"BRB-{carry_tube['yield_force']}-"
                                f"{carry_tube['product_length']}"
                            )
                        else:
                            carry_text = str(carry_out)
                            carry_info = None
                        dim = msp.add_linear_dim(
                            base=(plan_x + carry_out / 2, y + rect_height / 2 + 100),
                            p1=(plan_x, rect_top),
                            p2=(plan_x + carry_out, rect_top),
                            text=carry_text,
                            dimstyle="Standard",
                            dxfattribs={"layer": "DIMENSION", "color": 3, "lineweight": 25},
                            angle=0,
                        )
                        dim.render()
                        if carry_info:
                            carry_label = msp.add_text(
                                carry_info,
                                dxfattribs={"layer": "TEXT", "height": 120},
                            )
                            carry_label.set_placement(
                                (plan_x + carry_out / 2, y),
                                align=TextEntityAlignment.MIDDLE_CENTER,
                            )
                        plan_x += carry_out

                    # 计算剩余长度（废料或未续接尾料）
                    remaining_length = plan['remaining_length']
                    
                    # 绘制剩余长度的矩形
                    if remaining_length > 0:
                        rect_top = y + rect_height / 2
                        rect_bottom = y - rect_height / 2
                        
                        # 绘制剩余长度矩形（使用四条线，白色粗实线）
                        # 上边
                        msp.add_line(
                            (plan_x, rect_top),
                            (plan_x + remaining_length, rect_top),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        # 下边
                        msp.add_line(
                            (plan_x, rect_bottom),
                            (plan_x + remaining_length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        # 左边
                        msp.add_line(
                            (plan_x, rect_top),
                            (plan_x, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        # 右边
                        msp.add_line(
                            (plan_x + remaining_length, rect_top),
                            (plan_x + remaining_length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 35, "color": 7}
                        )
                        
                        # 显示剩余长度信息（使用线性标注）
                        # 如果余料会被用作拼接，则不加"余"字；否则加"余"字
                        # 只有当该方案的余料确实被后续方案使用时，才不加"余"字
                        
                        # 初始化变量
                        spliced_tube = None
                        found_splice = False
                        
                        # 首先尝试找到使用此余料的方管（在未合并方案中）
                        for p in stats_plans:
                            # 只在相同宽度的方案中查找
                            if p['tube_width'] == plan['tube_width']:
                                for tube in p['tubes']:
                                    if 'spliced_from' in tube and tube['spliced_from'] == remaining_length:
                                        # 进一步检查：确保使用此余料的方管的方案，其from_plan指向当前方案
                                        # 或者，检查当前方案的to_plan指向使用此余料的方案
                                        splice_info = ref_plan.get('splice_info', {})
                                        from_plan = splice_info.get('from_plan')
                                        to_plan = splice_info.get('to_plan')
                                        
                                        # 检查是否有明确的拼接关系
                                        has_splice_relation = False
                                        if to_plan and p['plan_id'] == to_plan:
                                            has_splice_relation = True
                                        elif 'splice_info' in p and p['splice_info'].get('from_plan') == ref_plan.get('plan_id'):
                                            has_splice_relation = True
                                        
                                        # 如果有余料长度匹配且有明确的拼接关系，则确认找到了使用此余料的方管
                                        if has_splice_relation or (not from_plan and not to_plan):
                                            # 找到使用此余料的方管
                                            spliced_tube = tube
                                            found_splice = True
                                            break
                                if found_splice:
                                    break
                        
                        if found_splice and spliced_tube:
                            # 显示为：余料(+剩余长度=需求方管长度)
                            remaining_text = (
                                f"{remaining_length}（+{spliced_tube['tube_length']}="
                                f"{spliced_tube['original_length']}）"
                            )
                        else:
                            # 没有找到使用此余料的方管，视为废料
                            remaining_text = f"余{remaining_length}"
                        
                        # 线性标注的两个端点（余料段的左右两端）
                        p1 = (plan_x, rect_top)  # 左端点
                        p2 = (plan_x + remaining_length, rect_top)  # 右端点
                        # 标注的基准点位置（余料段上方中间）
                        base = (plan_x + remaining_length / 2, y + rect_height / 2 + 100)  # 标注文本的位置，加高50
                        # 创建线性标注
                        dim = msp.add_linear_dim(
                            base=base,
                            p1=p1,
                            p2=p2,
                            text=remaining_text,
                            dimstyle="Standard",
                            dxfattribs={
                                "layer": "DIMENSION",
                                "color": 3,  # 绿色
                                "lineweight": 25
                            },
                            angle=0  # 水平标注
                        )
                        dim.render()
                        
                        # 在余料内部添加产品信息标注（格式：BRB-屈服力-产品长度）
                        if found_splice and spliced_tube:
                            tube_info = (
                                f"BRB-{spliced_tube['yield_force']}-"
                                f"{spliced_tube['product_length']}"
                            )
                            text_height = 120
                            leftover_label = msp.add_text(
                                tube_info,
                                dxfattribs={
                                    "layer": "TEXT",
                                    "height": text_height,
                                },
                            )
                            leftover_label.set_placement(
                                (plan_x + remaining_length / 2, y),
                                align=TextEntityAlignment.MIDDLE_CENTER,
                            )
                    
                    # 添加原材编号（显示该切割方案的实际数量）
                    raw_info = f"{plan['raw_materials']}根"
                    text_height = 120
                    # 计算方管下边缘位置：y - 方管高度的一半
                    tube_bottom = y - rect_height / 2
                    # 将原材数量放在方管下边缘下方，考虑文字高度（文字插入点是左下角）
                    text_y = tube_bottom - text_height - 50  # 增加50mm的间距
                    msp.add_text(
                        raw_info,
                        dxfattribs={
                            "layer": "TEXT",
                            "height": text_height,
                            "insert": (plan_start_x + plan['raw_length'] / 2, text_y)
                        }
                    )
                    
                    # 计算下一个方管的垂直中心位置：当前方管底部 - 间距(450) - 下一个方管高度的一半
                    # 由于无法预知下一个方管的高度，使用当前方管的高度作为参考
                    # 确保方管之间的实际间距为450mm（缩小100）
                    current_y = y - rect_height / 2 - 450 - rect_height / 2
                
                # 不同宽度组之间的间隔
                current_y -= 2000
            

            
            # 保存DXF文件到临时文件，然后读取到内存
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            try:
                # 保存到临时文件
                doc.saveas(temp_file_path)
                
                # 读取临时文件到内存
                dxf_stream = BytesIO()
                with open(temp_file_path, 'rb') as f:
                    dxf_stream.write(f.read())
                dxf_stream.seek(0)
            finally:
                # 清理临时文件
                import os
                if os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
            
            return dxf_stream, filename
        except Exception as e:
            alarm_logging.error(f"生成DXF文件时出错: {str(e)}")
            raise

# 测试代码
if __name__ == '__main__':
    import logging as _std_logging
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_log_utf8.txt')
    _fh = _std_logging.FileHandler(_log_path, encoding='utf-8', mode='w')
    _fh.setFormatter(_std_logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logging.addHandler(_fh)
    logging.setLevel(_std_logging.INFO)
    print(f"日志文件: {_log_path}")
    generator = TubeLayoutGenerator()

    json_path = os.path.join(os.path.dirname(__file__), "BRB-testdata", "河南大学龙子湖项目5.json")
    test_json = None
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            test_json = json.load(f)
        print(f"使用示例数据文件: {json_path}")
    else:
        print(f"未找到示例数据文件，使用内置回退数据: {json_path}")
        test_json = {
            "projectName": "北京第二实验学校（山东）",
            "parameterTables": [],
            "totalQuantity": 0,
            "version": "1.0"
        }

    try:
        dxf_stream, dxf_filename = generator.generate_tube_layout(
            test_json['projectName'],
            test_json['parameterTables']
        )

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, dxf_filename)
        try:
            with open(output_path, "wb") as f:
                f.write(dxf_stream.getvalue())
            print(f"DXF 已保存到: {output_path}")
        except PermissionError:
            alt = os.path.join(output_dir, f"_tmp_{dxf_filename}")
            with open(alt, "wb") as f:
                f.write(dxf_stream.getvalue())
            print(f"原路径被占用，DXF 已保存到: {alt}")
    except Exception as e:
        print(f"测试时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        for _h in list(logging.handlers):
            if isinstance(_h, _std_logging.FileHandler) and getattr(_h, 'baseFilename', '') == _log_path:
                _h.flush()
                _h.close()
                logging.removeHandler(_h)
