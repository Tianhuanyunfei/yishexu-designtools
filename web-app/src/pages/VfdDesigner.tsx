import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Zap, Download, FilePlus, FolderOpen, FileImage, FileText, Save, RefreshCw, ArrowLeft, Table2 } from 'lucide-react';
import { useToast } from '../components/Toast';

/* ------------------------------------------------------------------ 类型 */

interface Spec {
  bore: number;
  axis: number;
  label: string;
  available: boolean;
}

interface ParamItem {
  part: string;
  name: string;
  value: number;
  note: string;
}

interface LineEntity {
  type: 'LINE';
  layer: string;
  start: [number, number];
  end: [number, number];
}

interface ArcEntity {
  type: 'ARC';
  layer: string;
  center: [number, number];
  radius: number;
  start_angle: number;
  end_angle: number;
}

interface CircleEntity {
  type: 'CIRCLE';
  layer: string;
  center: [number, number];
  radius: number;
}

interface TextEntity {
  type: 'TEXT' | 'MTEXT';
  layer: string;
  text: string;
  /** MTEXT 的纯文本（不含 {\\W0.7;\\T1.1;...} 控制码），预览用 */
  plain?: string;
  /** MTEXT 宽度因子，预览按此压缩字宽 */
  width_factor?: number;
  position: [number, number];
  height: number;
  rotation: number;
}

interface DimEntity {
  type: 'DIMENSION';
  layer: string;
  dim_type: 'LINEAR' | 'RADIUS';
  value: number;
  override: string;
  angle: number;
  p1?: [number, number];
  p2?: [number, number];
  center?: [number, number];
  location: [number, number];
}

type Entity = LineEntity | ArcEntity | CircleEntity | TextEntity | DimEntity;

/** 可覆盖设计尺寸：on 为是否启用覆盖，value 为覆盖值文本 */
type Overrides = Record<string, { on: boolean; value: string }>;

interface Preview {
  entities: Entity[];
  axial: Record<string, number>;
  /** 未应用覆盖时的推导值，供启用覆盖的行显示被划掉的计算值 */
  axial_base: Record<string, number>;
  radial: Record<string, number>;
  bbox: { min_x: number; min_y: number; max_x: number; max_y: number };
  layers: string[];
}

/* -------------------------------------------------------------- 预览配色 */
const LAYER_COLORS: Record<string, string> = {
  '粗实线层': '#1f2937',
  '细实线层': '#6b7280',
  '中心线层': '#dc2626',
  '虚线层': '#a855f7',
  '尺寸线层': '#16a34a',
  '预览尺寸层': '#2563eb',
};

const colorOf = (layer: string) => LAYER_COLORS[layer] || '#9ca3af';

/** 设计尺寸：由设计位移与零件尺寸推导，不落盘，仅供查看 */
const DERIVED_FIELDS: Array<{ key: string; label: string; note: string; overridable?: boolean; input?: boolean }> = [
  { key: 'front_lug_length', label: '前吊耳长', note: '默认取零件尺寸表；前吊耳中心至前吊耳右侧边', overridable: true },
  { key: 'limit_displacement', label: '极限位移', note: '设计位移 < 100 时 ×1.5，否则 ×1.2' },
  { key: 'clearance', label: '腔体余量', note: '活塞运动到极限时与前盖或导向套的距离', input: true },
  { key: 'chamber', label: '前腔/后腔长度', note: '极限位移 + 腔体余量' },
  { key: 'cavity_length', label: '腔体长度', note: '前腔长 + 活塞宽 + 后腔长' },
  { key: 'lug_to_cover', label: '前吊耳至前盖', note: '防尘罩长度核算：下限 (11×极限位移 + 362) ÷ 9 后取到末位 0 或 5', overridable: true },
  { key: 'barrel_length', label: '前缸筒长度', note: '台阶端至前缸筒后端' },
  { key: 'rod_overhang', label: '轴后端伸出长', note: '前腔/后腔长度 − 5', overridable: true },
  { key: 'rod_to_rear_cover', label: '轴后端到后盖距离', note: '极限位移 + 25 + 10', overridable: true },
  { key: 'rear_barrel_length', label: '后缸筒长度', note: '轴后端伸出长 + 轴后端到后盖距离 + 后盖螺纹长度' },
  { key: 'rear_lug_length', label: '后吊耳长', note: '默认取零件尺寸表；后缸筒后端面至后吊耳中心', overridable: true },
  { key: 'rod_length', label: '轴的总长', note: '轴端螺纹里端至轴后端面' },
  { key: 'install_length', label: '安装距离', note: '前吊耳中心至后吊耳中心' },
];

/** 圆弧离散成折线点串（DXF 逆时针角度 → SVG 坐标，Y 取反） */
const arcPoints = (cx: number, cy: number, radius: number, a0: number, a1: number) => {
  const start = a0;
  let end = a1;
  while (end < start) end += 360;
  const steps = Math.max(8, Math.ceil((end - start) / 5));
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const a = ((start + ((end - start) * i) / steps) * Math.PI) / 180;
    pts.push(`${cx + radius * Math.cos(a)},${-(cy + radius * Math.sin(a))}`);
  }
  return pts.join(' ');
};

/** MTEXT 纯文本：去掉 {\\W0.7;\\T1.1;文字} 这类控制码，预览只显示文字 */
const mtextPlain = (entity: TextEntity) => {
  if (entity.plain !== undefined) return entity.plain;
  return entity.text.replace(/\{[^{}]*?;([^{}]*?)\}/g, '$1');
};

/** 尺寸文字：DXF 的 %%C 表示直径符号 */
const dimText = (entity: DimEntity) => {
  const raw = entity.override && entity.override !== '<>'
    ? entity.override
    : String(Math.round(entity.value * 1000) / 1000);
  return raw.replace(/%%C|%%c/g, 'Ø');
};

/** 尺寸文字的白底矩形：垫在文字下面，避免被图形线条干扰 */
const DimBackdrop: React.FC<{ cx: number; cy: number; text: string; fontSize: number }> = ({
  cx, cy, text, fontSize,
}) => {
  const w = text.length * fontSize * 0.68;
  const h = fontSize * 1.2;
  return (
    <rect
      x={cx - w / 2}
      y={cy - fontSize * 0.92}
      width={w}
      height={h}
      fill="#ffffff"
    />
  );
};

/** 尺寸线箭头：实心三角，顶点在 (ax, ay)，尖端指向 (dx, dy)，尾翼反向展开 */
const arrowPoints = (ax: number, ay: number, dx: number, dy: number, size: number) => {
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const w = size * 0.2;
  const bx = ax - ux * size;
  const by = ay - uy * size;
  return `${ax},${-ay} ${bx - uy * w},${-(by + ux * w)} ${bx + uy * w},${-(by - ux * w)}`;
};

/* ------------------------------------------------------------ 结构图预览 */

/** 预览高度上限（vh）：超过则按比例缩小，避免整页装不下 */
const PREVIEW_MAX_VH = 90;

/** MTEXT 在 DXF 里的插入点是左上角，SVG 的 y 是基线，需下移的比例（× 字高） */
const MTEXT_BASELINE_RATIO = 0.9;

const StructurePreview: React.FC<{ preview: Preview }> = ({ preview }) => {
  const { bbox, entities } = preview;

  const width = Math.max(bbox.max_x - bbox.min_x, 1);
  const height = Math.max(bbox.max_y - bbox.min_y, 1);
  const pad = Math.max(width, height) * 0.02;
  const viewBox = `${bbox.min_x - pad} ${-bbox.max_y - pad} ${width + 2 * pad} ${height + 2 * pad}`;
  const fontSize = Math.max(width, height) / 70;
  const dimFontSize = fontSize * 0.72;   // 尺寸文字略小于图形注释文字，避免抢画面
  // 预览按屏幕高度限高：宽高比由内容决定，max-width 用 vh 表达，保证整页放得下
  const maxWidthVh = (width / height) * PREVIEW_MAX_VH;

  return (
    <svg
      className="w-full bg-white border border-gray-200 rounded-lg"
      style={{ height: 'auto', maxWidth: `${maxWidthVh.toFixed(2)}vh`, margin: '0 auto', display: 'block' }}
      viewBox={viewBox}
      preserveAspectRatio="xMidYMid meet"
    >
      {entities.map((entity, index) => {
        const stroke = colorOf(entity.layer);

        if (entity.type === 'LINE') {
          return (
            <line
              key={index}
              x1={entity.start[0]}
              y1={-entity.start[1]}
              x2={entity.end[0]}
              y2={-entity.end[1]}
              stroke={stroke}
              strokeWidth={entity.layer === '粗实线层' ? fontSize * 0.09 : fontSize * 0.05}
            />
          );
        }

        if (entity.type === 'CIRCLE') {
          return (
            <circle
              key={index}
              cx={entity.center[0]}
              cy={-entity.center[1]}
              r={entity.radius}
              fill="none"
              stroke={stroke}
              strokeWidth={fontSize * 0.06}
            />
          );
        }

        if (entity.type === 'ARC') {
          return (
            <polyline
              key={index}
              points={arcPoints(entity.center[0], entity.center[1], entity.radius, entity.start_angle, entity.end_angle)}
              fill="none"
              stroke={stroke}
              strokeWidth={fontSize * 0.06}
            />
          );
        }

        // TEXT / MTEXT：指引线注释、标题栏等文字
        if (entity.type === 'TEXT' || entity.type === 'MTEXT') {
          const tx = entity.position[0];
          // MTEXT 的插入点在左上角，预览要按基线画，故整体下移约一个字高
          const drop = entity.type === 'MTEXT' ? (entity.height || fontSize) * MTEXT_BASELINE_RATIO : 0;
          const ty = -entity.position[1] + drop;
          const wf = entity.type === 'MTEXT' ? entity.width_factor ?? 1 : 1;
          const transforms = [
            entity.rotation ? `rotate(${-entity.rotation} ${tx} ${ty})` : '',
            wf !== 1 ? `translate(${tx} 0) scale(${wf} 1) translate(${-tx} 0)` : '',
          ].filter(Boolean).join(' ');
          return (
            <text
              key={index}
              x={tx}
              y={ty}
              fill={stroke}
              fontSize={entity.height || fontSize}
              textAnchor="start"
              transform={transforms || undefined}
            >
              {entity.type === 'MTEXT' ? mtextPlain(entity) : entity.text}
            </text>
          );
        }

        // 余下分支只处理尺寸实体
        if (entity.type !== 'DIMENSION') return null;

        // DIMENSION：预览只画尺寸线与尺寸文字
        if (entity.dim_type === 'RADIUS' && entity.center) {
          const a = (entity.angle * Math.PI) / 180;
          const ex = entity.center[0] + entity.value * Math.cos(a);
          const ey = entity.center[1] + entity.value * Math.sin(a);
          const ty = -ey - dimFontSize * 0.4;    // 抬离尺寸线，避免压线
          const arrow = dimFontSize * 0.9;
          const label = dimText(entity);
          // 出圆弧后折出一段水平线，文字骑在水平线上方，并整体往所在侧（左/右）平移
          const dir = Math.cos(a) >= 0 ? 1 : -1;
          const tail = label.length * dimFontSize * 0.68 + dimFontSize * 0.6;
          const hx = ex + dir * tail;
          return (
            <g key={index}>
              <line
                x1={entity.center[0]}
                y1={-entity.center[1]}
                x2={ex}
                y2={-ey}
                stroke={stroke}
                strokeWidth={fontSize * 0.05}
              />
              <polygon
                points={arrowPoints(ex, ey, ex - entity.center[0], ey - entity.center[1], arrow)}
                fill={stroke}
              />
              <line
                x1={ex}
                y1={-ey}
                x2={hx}
                y2={-ey}
                stroke={stroke}
                strokeWidth={fontSize * 0.05}
              />
              <DimBackdrop cx={(ex + hx) / 2} cy={ty} text={label} fontSize={dimFontSize} />
              <text x={(ex + hx) / 2} y={ty} fill={stroke} fontSize={dimFontSize} textAnchor="middle">
                {label}
              </text>
            </g>
          );
        }

        const p1 = entity.p1 || entity.location;
        const p2 = entity.p2 || entity.location;
        const loc = entity.location;
        const isVertical = Math.abs(entity.angle - 90) < 1e-6;

        const x1 = isVertical ? loc[0] : p1[0];
        const y1 = isVertical ? p1[1] : loc[1];
        const x2 = isVertical ? loc[0] : p2[0];
        const y2 = isVertical ? p2[1] : loc[1];

        // 尺寸界线：自被测点引至尺寸线
        const extLines: [number, number, number, number][] = isVertical
          ? [
              [p1[0], p1[1], loc[0], p1[1]],
              [p2[0], p2[1], loc[0], p2[1]],
            ]
          : [
              [p1[0], p1[1], p1[0], loc[1]],
              [p2[0], p2[1], p2[0], loc[1]],
            ];

        // 尺寸线两端的箭头：尖端在被测点，箭尾朝尺寸线内侧
        const arrow = dimFontSize * 0.9;
        const dimArrow = (px: number, py: number, qx: number, qy: number, k: string) => (
          <polygon key={k} points={arrowPoints(px, py, px - qx, py - qy, arrow)} fill={stroke} />
        );

        return (
          <g key={index}>
            {extLines.map(([ax, ay, bx, by], i) => (
              <line
                key={`ext${i}`}
                x1={ax}
                y1={-ay}
                x2={bx}
                y2={-by}
                stroke={stroke}
                strokeWidth={fontSize * 0.035}
              />
            ))}
            <line
              x1={x1}
              y1={-y1}
              x2={x2}
              y2={-y2}
              stroke={stroke}
              strokeWidth={fontSize * 0.05}
            />
            {dimArrow(x1, y1, x2, y2, 'arr1')}
            {dimArrow(x2, y2, x1, y1, 'arr2')}
            <DimBackdrop
              cx={(x1 + x2) / 2}
              cy={-((y1 + y2) / 2) - dimFontSize * 0.4}
              text={dimText(entity)}
              fontSize={dimFontSize}
            />
            <text
              x={(x1 + x2) / 2}
              y={-((y1 + y2) / 2) - dimFontSize * 0.4}
              fill={stroke}
              fontSize={dimFontSize}
              textAnchor="middle"
            >
              {dimText(entity)}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

/* ------------------------------------------------------------------ 页面 */

/** 缸径/轴径持久化：从 localStorage 读取，空值或非法值视为未选 */
const readSize = (key: string): number | null => {
  const raw = localStorage.getItem(key);
  if (raw === null || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
};

/** 覆盖值持久化：从 localStorage 读取，内容损坏时退回空对象 */
const readOverrides = (): Overrides => {
  const raw = localStorage.getItem('vfd_overrides');
  if (!raw) return {};
  try {
    const data = JSON.parse(raw);
    return data && typeof data === 'object' ? (data as Overrides) : {};
  } catch {
    return {};
  }
};

const VfdDesigner: React.FC = () => {
  const { showToast } = useToast();

  const [projectName, setProjectName] = useState(() => localStorage.getItem('vfd_projectName') || '');
  const [quantity, setQuantity] = useState(() => localStorage.getItem('vfd_quantity') || '');
  const [force, setForce] = useState(() => localStorage.getItem('vfd_force') || '');
  const [displacement, setDisplacement] = useState(() => localStorage.getItem('vfd_displacement') || '');
  const [clearance, setClearance] = useState(() => localStorage.getItem('vfd_clearance') || '30');

  const [specs, setSpecs] = useState<Spec[]>([]);
  const [bore, setBore] = useState<number | null>(() => readSize('vfd_bore'));
  const [axis, setAxis] = useState<number | null>(() => readSize('vfd_axis'));

  const [params, setParams] = useState<ParamItem[]>([]);
  const [values, setValues] = useState<Record<string, number>>({});

  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const firstLoad = useRef(true);

  /** 视图：主页面 / 零件尺寸表（二级页面） */
  const [view, setView] = useState<'main' | 'parts'>('main');

  // 可覆盖设计尺寸：on 为是否启用覆盖，value 为覆盖值文本（空串表示未填）
  const [overrides, setOverrides] = useState<Overrides>(readOverrides);

  useEffect(() => { localStorage.setItem('vfd_projectName', projectName); }, [projectName]);
  useEffect(() => { localStorage.setItem('vfd_quantity', quantity); }, [quantity]);
  useEffect(() => { localStorage.setItem('vfd_force', force); }, [force]);
  useEffect(() => { localStorage.setItem('vfd_displacement', displacement); }, [displacement]);
  useEffect(() => { localStorage.setItem('vfd_clearance', clearance); }, [clearance]);
  useEffect(() => {
    localStorage.setItem('vfd_bore', bore === null ? '' : String(bore));
  }, [bore]);
  useEffect(() => {
    localStorage.setItem('vfd_axis', axis === null ? '' : String(axis));
  }, [axis]);
  useEffect(() => {
    localStorage.setItem('vfd_overrides', JSON.stringify(overrides));
  }, [overrides]);

  const modelName = `VFD-${force || '?'}-${displacement || '?'}`;

  /* --- 规格库 --- */
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/vfd/specs');
        const data = await res.json();
        if (data.status !== 'success') throw new Error(data.message || '读取规格表失败');
        setSpecs(data.specs || []);
      } catch (error) {
        showToast(error instanceof Error ? error.message : '读取规格表失败', 'error');
      }
    })();
  }, [showToast]);

  const axes = useMemo(
    () => specs.filter(s => s.bore === bore).map(s => s.axis),
    [specs, bore]
  );

  /* --- 零件尺寸表：只在缸径与轴径都选定后才读取（数值为后台维护的默认尺寸） --- */
  useEffect(() => {
    if (bore === null || axis === null) {
      setParams([]);
      setValues({});
      setPreview(null);
      return;
    }
    (async () => {
      try {
        const res = await fetch(`/api/vfd/params?bore=${bore}&axis=${axis}`);
        const data = await res.json();
        if (data.status !== 'success') throw new Error(data.message || '读取零件尺寸失败');
        const list: ParamItem[] = data.params || [];
        const dict: Record<string, number> = {};
        list.forEach(item => { dict[item.name] = item.value; });
        setParams(list);
        setValues(dict);
        firstLoad.current = true;
      } catch (error) {
        setParams([]);
        setValues({});
        showToast(error instanceof Error ? error.message : '读取零件尺寸失败', 'error');
      }
    })();
  }, [bore, axis, showToast]);

  /* --- 覆盖值：仅取已启用且有输入值的项，传给后端参与全部下游推导 --- */
  const overridePayload = useMemo(() => {
    const out: Record<string, number> = {};
    Object.entries(overrides).forEach(([key, item]) => {
      if (!item.on) return;
      const n = Number(item.value);
      if (item.value !== '' && Number.isFinite(n)) out[key] = n;
    });
    return out;
  }, [overrides]);

  /* --- 改尺寸立即刷新预览（防抖） --- */
  useEffect(() => {
    if (!Object.keys(values).length) { setPreview(null); return; }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch('/api/vfd/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ values, displacement, clearance, overrides: overridePayload, projectName, modelName, quantity }),
        });
        const data = await res.json();
        if (data.status !== 'success') throw new Error(data.message || '生成预览失败');
        setPreview(data.preview);
      } catch (error) {
        showToast(error instanceof Error ? error.message : '生成预览失败', 'error');
      }
    }, firstLoad.current ? 0 : 400);
    firstLoad.current = false;
    return () => clearTimeout(timer);
  }, [values, displacement, clearance, overridePayload, projectName, modelName, quantity, showToast]);

  const partGroups = useMemo(() => {
    const groups: Array<{ part: string; items: ParamItem[] }> = [];
    params.forEach(item => {
      const last = groups[groups.length - 1];
      if (last && last.part === item.part) last.items.push(item);
      else groups.push({ part: item.part, items: [item] });
    });
    return groups;
  }, [params]);

  /* --- 覆盖开关与覆盖值 --- */
  const setOverride = (key: string, patch: { on?: boolean; value?: string }) => {
    setOverrides(prev => {
      const cur = prev[key] ?? { on: false, value: '' };
      return { ...prev, [key]: { ...cur, ...patch } };
    });
  };

  /* --- 生成结构图 DXF 并下载 --- */
  const handleGenerateDrawing = async () => {
    if (bore === null || axis === null) {
      showToast('请先选择缸径与轴径', 'error');
      return;
    }
    if (!quantity.trim()) {
      showToast('请先填写产品数量', 'error');
      return;
    }
    try {
      setBusy(true);
      const res = await fetch('/api/vfd/structure-dxf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bore, axis, values, modelName, displacement, clearance, overrides: overridePayload, projectName, quantity }),
      });
      const data = await res.json();
      if (data.status !== 'success') throw new Error(data.message || '生成图纸失败');

      const file = data.result;
      const dl = await fetch(`/api/download/file?path=${encodeURIComponent(file.path)}`);
      if (!dl.ok) throw new Error('文件下载失败');
      const blob = await dl.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('结构图生成完成', 'success');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '生成图纸失败', 'error');
    } finally {
      setBusy(false);
    }
  };

  /* --- 项目：新建 / 打开 / 保存 --- */

  /** 是否有内容会被新建操作清掉 */
  const projectDirty = () => Boolean(projectName || quantity || force || displacement || bore !== null);

  const handleNewProject = () => {
    if (projectDirty() && !window.confirm('当前项目的内容将被清空，确定要新建项目吗？')) return;
    setProjectName('');
    setQuantity('');
    setForce('');
    setDisplacement('');
    setClearance('');
    setBore(null);
    setAxis(null);
    setOverrides({});
    setParams([]);
    setValues({});
    setPreview(null);
    setView('main');
    showToast('已新建项目', 'success');
  };

  const handleSaveProject = () => {
    const payload = {
      projectName, modelName, force, displacement, clearance, bore, axis, quantity,
      overrides,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName || modelName}_项目.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast('项目已保存', 'success');
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleOpenProject = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    /** 项目文件由用户提供，缸径/轴径统一按数字处理，非法值视为未选 */
    const toSize = (raw: unknown): number | null => {
      const n = Number(raw);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    reader.onload = () => {
      try {
        const data = JSON.parse(String(reader.result));
        setProjectName(data.projectName ?? '');
        setQuantity(data.quantity ?? '');
        setForce(data.force ?? '');
        setDisplacement(data.displacement ?? '');
        setClearance(data.clearance ?? '');
        setOverrides(data.overrides ?? {});
        // 零件尺寸由缸径/轴径决定，只恢复选型，尺寸表由后端重新读取
        setBore(toSize(data.bore));
        setAxis(toSize(data.axis));
        setView('main');
        showToast('项目已打开', 'success');
      } catch {
        showToast('项目文件格式有误', 'error');
      }
    };
    reader.readAsText(file);
    event.target.value = '';
  };

  return (
    <div className="space-y-6 px-4 md:px-12 xl:px-20">
      {/* 第一行：项目名称 + 操作按钮 */}
      <div className="card p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex items-center space-x-3 mr-2">
            <Zap className="h-8 w-8 text-green-600" />
            <h1 className="text-2xl font-bold text-gray-900">粘滞阻尼器设计</h1>
          </div>
          <div className="flex-1 min-w-[240px]">
            <label className="form-label">项目名称</label>
            <input
              type="text"
              className="input-field"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="请输入项目名称"
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary flex items-center space-x-2" onClick={handleNewProject} disabled={busy}>
              <FilePlus className="h-4 w-4" />
              <span>新建项目</span>
            </button>
            <button
              className="btn-secondary flex items-center space-x-2"
              onClick={() => fileInputRef.current?.click()}
            >
              <FolderOpen className="h-4 w-4" />
              <span>打开项目</span>
            </button>
            <button className="btn-secondary flex items-center space-x-2" onClick={handleSaveProject}>
              <Save className="h-4 w-4" />
              <span>保存项目</span>
            </button>
            <input ref={fileInputRef} type="file" accept=".json" className="hidden" onChange={handleOpenProject} />
            <button className="btn-secondary flex items-center space-x-2" onClick={handleGenerateDrawing} disabled={busy}>
              <Download className="h-4 w-4" />
              <span>生成图纸</span>
            </button>
            <button
              className="btn-secondary flex items-center space-x-2"
              onClick={() => showToast('轮廓图接口待接入', 'info')}
            >
              <FileImage className="h-4 w-4" />
              <span>生成轮廓图</span>
            </button>
            <button
              className="btn-secondary flex items-center space-x-2"
              onClick={() => showToast('材料单接口待接入', 'info')}
            >
              <FileText className="h-4 w-4" />
              <span>生成材料单</span>
            </button>
          </div>
        </div>
      </div>

      {/* 参数表区（每张表独占整个区域，点表头切换） */}
      <div className="card overflow-hidden">
        <div className="flex border-b border-gray-200 bg-gray-50">
          <div className="px-6 py-3 text-sm font-semibold text-green-700 border-b-2 border-green-600 -mb-px bg-white">
            参数表
          </div>
        </div>

        <div className="p-6 space-y-5">
          {/* 型号：VFD-[力]-[设计位移] */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div>
              <label className="form-label">力（kN）</label>
              <input
                type="number"
                className="input-field"
                value={force}
                onChange={(e) => setForce(e.target.value)}
                placeholder="如 1000"
              />
            </div>
            <div>
              <label className="form-label">设计位移（mm）</label>
              <input
                type="number"
                className="input-field"
                value={displacement}
                onChange={(e) => setDisplacement(e.target.value)}
                placeholder="如 30"
              />
            </div>
            <div>
              <label className="form-label">腔体余量（mm）</label>
              <input
                type="number"
                className="input-field"
                value={clearance}
                onChange={(e) => setClearance(e.target.value)}
                placeholder="如 30"
              />
            </div>
            <div>
              <label className="form-label">型号</label>
              <div className="px-4 py-2 bg-gray-50 border border-gray-300 rounded-lg font-semibold text-gray-800">
                {modelName}
              </div>
            </div>
            <div>
              <label className="form-label">产品数量</label>
              <input
                type="text"
                className="input-field"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder=""
              />
            </div>
          </div>

          {/* 缸径 → 轴径（联动） */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="form-label">缸径（mm）</label>
              <select
                className="input-field"
                value={bore ?? ''}
                onChange={(e) => {
                  const nextBore = Number(e.target.value);
                  setBore(nextBore);
                  const axisList = specs.filter(s => s.bore === nextBore).map(s => s.axis);
                  setAxis(axisList[0] ?? null);
                }}
              >
                <option value="" disabled>请选择缸径</option>
                {Array.from(new Set(specs.map(s => s.bore))).map(b => (
                  <option key={b} value={b}>缸径{b}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">轴径（mm）</label>
              <select
                className="input-field"
                value={axis ?? ''}
                onChange={(e) => setAxis(Number(e.target.value))}
              >
                <option value="" disabled>请选择轴径</option>
                {axes.map(r => (
                  <option key={r} value={r}>轴径{r}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2 flex items-center gap-3">
              <button
                className="btn-secondary flex items-center space-x-2"
                onClick={() => setView('parts')}
                disabled={bore === null || axis === null}
              >
                <Table2 className="h-4 w-4" />
                <span>零件尺寸表</span>
              </button>
              <span className="text-sm text-gray-500">
                零件尺寸表为此型号的默认尺寸，由后台维护，网页端不可修改
              </span>
            </div>
          </div>
        </div>
      </div>

      {view === 'parts' ? (
        /* 二级页面：零件尺寸表（只读，后台维护） */
        <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center space-x-3">
              <button
                className="btn-secondary flex items-center space-x-2 py-1"
                onClick={() => setView('main')}
              >
                <ArrowLeft className="h-4 w-4" />
                <span>返回</span>
              </button>
              <span className="text-sm font-semibold text-gray-700">零件尺寸表</span>
              <span className="text-sm text-gray-500">{modelName}</span>
            </div>
            <span className="text-xs text-gray-500">
              {bore === null || axis === null
                ? '请先选择缸径与轴径'
                : '此型号的默认尺寸，仅后台可更改；前吊耳长 / 后吊耳长可在设计尺寸中覆盖'}
            </span>
          </div>
          <div className="max-h-[640px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left px-6 py-2 font-semibold text-gray-700 w-36">零件名</th>
                  <th className="text-left px-6 py-2 font-semibold text-gray-700 w-48">尺寸名</th>
                  <th className="text-left px-6 py-2 font-semibold text-gray-700 w-32">值</th>
                  <th className="text-left px-6 py-2 font-semibold text-gray-700">说明</th>
                </tr>
              </thead>
              <tbody>
                {partGroups.map(group =>
                  group.items.map((item, index) => (
                    <tr key={item.name} className="border-t border-gray-100">
                      {index === 0 && (
                        <td
                          rowSpan={group.items.length}
                          className="px-6 py-1.5 text-gray-800 font-medium align-middle border-r border-gray-100"
                        >
                          {group.part}
                        </td>
                      )}
                      <td className="px-6 py-1.5 text-gray-800">{item.name}</td>
                      <td className="px-6 py-1.5 text-gray-900 font-medium">{values[item.name] ?? '—'}</td>
                      <td className="px-6 py-1.5 text-gray-500">{item.note}</td>
                    </tr>
                  ))
                )}
                {partGroups.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-gray-500">
                      {bore === null || axis === null ? '请先选择缸径与轴径' : '暂无数据'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* 结构图预览在左、设计尺寸在右，预览宽度受列宽约束后自然收窄 */
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px] gap-4 items-start">
          {/* 右侧：设计尺寸（自动推导，可覆盖项支持手工覆盖，不落盘） */}
          <div className="card overflow-hidden xl:order-2">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700">
              设计尺寸（自动推导）
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr className="border-b border-gray-200 text-gray-500">
                  <th className="text-left px-3 py-1.5 font-semibold">尺寸名</th>
                  <th className="text-left px-3 py-1.5 font-semibold">推导值（mm）</th>
                  <th className="text-left px-3 py-1.5 font-semibold">覆盖</th>
                </tr>
              </thead>
              <tbody>
                {DERIVED_FIELDS.map(field => {
                  const ov = overrides[field.key];
                  const enabled = Boolean(ov?.on);
                  // 启用覆盖的行显示被划掉的公式推导值（axial_base），
                  // 其余行显示图纸实际生效值（axial，已含覆盖引起的下游变化）
                  const source = preview ? (enabled ? (preview.axial_base ?? preview.axial) : preview.axial) : null;
                  const computed = field.input
                    ? (clearance === '' ? null : Number(clearance))
                    : (source ? Math.round((source[field.key] ?? 0) * 1000) / 1000 : null);
                  return (
                    <tr key={field.key} className={`border-t border-gray-100${field.input ? ' bg-amber-50/40' : ''}`}>
                      <td className="px-3 py-1.5 text-gray-800">
                        <span className="flex items-center space-x-1">
                          <span>{field.label}</span>
                          {field.note && (
                            <span
                              title={field.note}
                              className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-gray-300 text-[10px] leading-none text-gray-400 cursor-help select-none"
                            >
                              ?
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-gray-800 font-medium whitespace-nowrap">
                        {enabled ? (
                          <span className="text-gray-400 line-through mr-2">{computed ?? '—'}</span>
                        ) : (
                          <span>{computed ?? '—'}</span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 whitespace-nowrap">
                        {field.input ? (
                          <input
                            type="number"
                            className="input-field py-0.5 px-2 text-sm w-24"
                            value={clearance}
                            onChange={(e) => setClearance(e.target.value)}
                            placeholder="如 30"
                          />
                        ) : field.overridable ? (
                          /* 小框内填了数字即代表覆盖，清空即取消覆盖 */
                          <input
                            type="number"
                            className="input-field py-0.5 px-2 text-sm w-20"
                            value={ov?.value ?? ''}
                            onChange={(e) =>
                              setOverride(field.key, { value: e.target.value, on: e.target.value.trim() !== '' })
                            }
                          />
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* 左侧：带尺寸矢量图 */}
          <div className="card p-4 flex flex-col xl:order-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-gray-700">
                结构图预览（1:1）
              </span>
              <button
                className="text-sm text-brb-blue-600 hover:underline flex items-center space-x-1"
                onClick={() => setValues({ ...values })}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>刷新</span>
              </button>
            </div>
            {preview ? (
              <>
                <StructurePreview preview={preview} />
                <p className="mt-2 text-xs text-gray-500">
                  <span className="inline-block w-3 h-3 rounded-sm align-[-1px] mr-1" style={{ backgroundColor: LAYER_COLORS['预览尺寸层'] }} />
                  蓝色标注为前腔长度、活塞宽度、后腔长度，仅用于预览核对，生成图纸时不输出此尺寸。
                </p>
              </>
            ) : (
              <div className="flex-1 min-h-[420px] flex items-center justify-center bg-gray-50 rounded-lg text-gray-500">
                暂无预览
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VfdDesigner;
