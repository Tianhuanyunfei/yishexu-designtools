import React from 'react';

export type WangSectionValues = {
  width: string;
  height: string;
  thickness: string;
  weld: string;
  tubeWidth: string;
  tubeThickness: string;
};

type FieldKey = keyof WangSectionValues;

type Props = {
  values: WangSectionValues;
  onChange: (field: FieldKey, value: string) => void;
  /** wang=王字（三横），shi=十字（一横） */
  variant?: 'wang' | 'shi';
  /** 屈服承载力 Fy (kN)，用于偏差计算 */
  designForce?: string;
  /** 屈服强度 (MPa)，默认 294，可改 */
  yieldStrength?: string;
  onYieldStrengthChange?: (value: string) => void;
};

/** 与 BRB结构核算一致：工=2翼缘+腹板，丨=高×厚；FY=A×fy/1000；偏差=(FY-Fy)/Fy */
function calcCoreFyCheck(
  variant: 'wang' | 'shi',
  width: string,
  height: string,
  thickness: string,
  designForce: string,
  yieldStrength: string,
): { theoreticalFy: number | null; deviationPercentage: number | null } {
  const b = parseFloat(width);
  const h = parseFloat(height);
  const t = parseFloat(thickness);
  const Fy = parseFloat(designForce);
  const f_y = parseFloat(yieldStrength);
  if (![b, h, t, f_y].every((n) => Number.isFinite(n) && n > 0)) {
    return { theoreticalFy: null, deviationPercentage: null };
  }
  // 十→丨；王（丨）/王（工）→工
  const coreArea = variant === 'shi' ? h * t : 2 * (b * t) + (h - 2 * t) * t;
  const theoreticalFy = Math.round((coreArea * f_y) / 1000);
  const deviationPercentage =
    Number.isFinite(Fy) && Fy !== 0
      ? parseFloat((((theoreticalFy - Fy) / Fy) * 100).toFixed(2))
      : null;
  return { theoreticalFy, deviationPercentage };
}


const baseInputClass =
  'px-1 text-center text-[14px] leading-none bg-white border border-gray-500 rounded-sm shadow-sm focus:ring-1 focus:ring-brb-blue-500 focus:border-brb-blue-500 appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden placeholder:text-[13px] placeholder:text-gray-600';

function FieldInput({
  field,
  value,
  onChange,
  placeholder,
  vertical = false,
  className = '',
}: {
  field: FieldKey;
  value: string;
  onChange: (field: FieldKey, value: string) => void;
  placeholder: string;
  vertical?: boolean;
  className?: string;
}) {
  const input = (
    <input
      type="number"
      title={placeholder}
      aria-label={placeholder}
      placeholder={placeholder}
      className={`${baseInputClass} ${
        vertical ? 'h-[30px] w-[72px] shrink-0 -rotate-90' : 'h-[30px] w-[64px]'
      }`}
      style={{ MozAppearance: 'textfield' } as React.CSSProperties}
      onWheel={(e) => (e.target as HTMLInputElement).blur()}
      onDragStart={(e) => e.stopPropagation()}
      value={value}
      onChange={(e) => onChange(field, e.target.value)}
    />
  );

  if (vertical) {
    return (
      <div className={`absolute z-10 flex h-[72px] w-[30px] items-center justify-center ${className}`}>
        {input}
      </div>
    );
  }

  return <div className={`absolute z-10 ${className}`}>{input}</div>;
}

/**
 * 王（丨）/ 王（工）/ 十 截面参数：按工程示意图布局填写。
 * 十与王字的区别：内芯为「十」（一横一竖），其余标注相同。
 */
const WangSectionParams: React.FC<Props> = ({
  values,
  onChange,
  variant = 'wang',
  designForce = '',
  yieldStrength = '294',
  onYieldStrengthChange,
}) => {
  const isShi = variant === 'shi';
  const { theoreticalFy, deviationPercentage } = calcCoreFyCheck(
    variant,
    values.width,
    values.height,
    values.thickness,
    designForce,
    yieldStrength || '294',
  );
  const deviationAbs = deviationPercentage == null ? null : Math.abs(deviationPercentage);
  const deviationClass =
    deviationAbs == null
      ? 'text-gray-500'
      : deviationAbs <= 5
        ? 'text-green-700'
        : deviationAbs <= 10
          ? 'text-orange-600'
          : 'text-red-600';
  // viewBox 坐标（对齐参考图；shiftY 整体下移）
  const shiftX = 22;
  const shiftY = 20;
  const ox = 92 + shiftX; // 方管外框左
  const oy = 78 + shiftY; // 方管外框上
  const os = 150; // 方管外边长
  const wall = 10;
  const ix = ox + wall;
  const iy = oy + wall;
  const isz = os - wall * 2;

  const barW = 96;
  const barH = 14;
  const stemW = 16;
  const wangL = ox + (os - barW) / 2;
  const stemX = ox + (os - stemW) / 2;
  const topY = oy + 26;
  const midY = oy + os / 2 - barH / 2;
  const botY = oy + os - 26 - barH;
  // 截面宽度尺寸线指到的横板顶边：王=上横，十=中横
  const widthBarY = isShi ? midY : topY;
  // 截面高度引出线搭到：王=横板左缘，十=竖腹板左缘
  const heightReachX = isShi ? stemX : wangL;

  // 间距 45：最内侧板材厚度线不动，只向外推外侧两条
  const dimGap = 45;
  const leftThickX = 104;
  const leftHeightX = leftThickX - dimGap; // 59
  const leftTubeX = leftHeightX - dimGap; // 14
  const weldStartX = 84;

  const topOuterY = 14 + shiftY;
  const topInnerY = 62 + shiftY;

  return (
    <div className="-mx-2 border-y border-gray-200 bg-white">
      {/* 所有标签 className 都在下方统一改 */}
      <div className="relative w-full" style={{ height: 300 }}>
        <svg
          viewBox="0 0 280 295"
          className="absolute inset-0 h-full w-full text-gray-900"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden
        >
          <defs>
            <marker id="aE" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
              <path d="M0,0 L5,2.5 L0,5 Z" fill="currentColor" />
            </marker>
            <marker id="aS" markerWidth="5" markerHeight="5" refX="1" refY="2.5" orient="auto">
              <path d="M5,0 L0,2.5 L5,5 Z" fill="currentColor" />
            </marker>
          </defs>

          {/* 方管 */}
          <rect x={ox} y={oy} width={os} height={os} rx="5" fill="none" stroke="currentColor" strokeWidth="2.2" />
          <rect x={ix} y={iy} width={isz} height={isz} fill="none" stroke="currentColor" strokeWidth="1.4" />

          {/* 内芯：王=三横一竖；十=一横一竖 */}
          <rect x={stemX} y={topY} width={stemW} height={botY + barH - topY} fill="currentColor" />
          {!isShi && <rect x={wangL} y={topY} width={barW} height={barH} fill="currentColor" />}
          <rect x={wangL} y={midY} width={barW} height={barH} fill="currentColor" />
          {!isShi && <rect x={wangL} y={botY} width={barW} height={barH} fill="currentColor" />}

          {/* 顶：方管宽度 */}
          <line x1={ox} y1={topOuterY} x2={ox + os} y2={topOuterY} stroke="currentColor" strokeWidth="1.05"
            markerStart="url(#aS)" markerEnd="url(#aE)" />
          <line x1={ox} y1={oy} x2={ox} y2={topOuterY - 4} stroke="currentColor" strokeWidth="0.85" />
          <line x1={ox + os} y1={oy} x2={ox + os} y2={topOuterY - 4} stroke="currentColor" strokeWidth="0.85" />

          {/* 顶：截面宽度 */}
          <line x1={wangL} y1={topInnerY} x2={wangL + barW} y2={topInnerY} stroke="currentColor" strokeWidth="1.05"
            markerStart="url(#aS)" markerEnd="url(#aE)" />
          <line x1={wangL} y1={widthBarY} x2={wangL} y2={topInnerY - 4} stroke="currentColor" strokeWidth="0.85" />
          <line x1={wangL + barW} y1={widthBarY} x2={wangL + barW} y2={topInnerY - 4} stroke="currentColor" strokeWidth="0.85" />

          {/* 左：方管宽度（外框全高，与顶部同步） */}
          <line x1={leftTubeX} y1={oy} x2={leftTubeX} y2={oy + os} stroke="currentColor" strokeWidth="1.05"
            markerStart="url(#aS)" markerEnd="url(#aE)" />
          <line x1={leftTubeX} y1={oy} x2={ox} y2={oy} stroke="currentColor" strokeWidth="0.85" />
          <line x1={leftTubeX} y1={oy + os} x2={ox} y2={oy + os} stroke="currentColor" strokeWidth="0.85" />

          {/* 左：截面高度 */}
          <line x1={leftHeightX} y1={topY} x2={leftHeightX} y2={botY + barH} stroke="currentColor" strokeWidth="1.05"
            markerStart="url(#aS)" markerEnd="url(#aE)" />
          <line x1={leftHeightX} y1={topY} x2={heightReachX} y2={topY} stroke="currentColor" strokeWidth="0.85" />
          <line x1={leftHeightX} y1={botY + barH} x2={heightReachX} y2={botY + barH} stroke="currentColor" strokeWidth="0.85" />

          {/* 左：板材厚度（中间板） */}
          <line x1={leftThickX} y1={midY} x2={leftThickX} y2={midY + barH} stroke="currentColor" strokeWidth="1.05"
            markerStart="url(#aS)" markerEnd="url(#aE)" />
          <line x1={leftThickX} y1={midY} x2={wangL} y2={midY} stroke="currentColor" strokeWidth="0.85" />
          <line x1={leftThickX} y1={midY + barH} x2={wangL} y2={midY + barH} stroke="currentColor" strokeWidth="0.85" />

          {/* 焊缝：从左下指向中板与腹板交接处 */}
          <line
            x1={weldStartX}
            y1={botY + barH + 36}
            x2={stemX + stemW / 2}
            y2={midY + barH}
            stroke="currentColor"
            strokeWidth="1.05"
            markerEnd="url(#aE)"
          />

          {/* 底右：方管厚度 */}
          <line
            x1={ox + os - wall}
            y1={oy + os + 26}
            x2={ox + os}
            y2={oy + os + 26}
            stroke="currentColor"
            strokeWidth="1.05"
            markerStart="url(#aS)"
            markerEnd="url(#aE)"
          />
          <line
            x1={ox + os - wall}
            y1={oy + os}
            x2={ox + os - wall}
            y2={oy + os + 32}
            stroke="currentColor"
            strokeWidth="0.85"
          />
          <line
            x1={ox + os}
            y1={oy + os}
            x2={ox + os}
            y2={oy + os + 32}
            stroke="currentColor"
            strokeWidth="0.85"
          />
        </svg>

        {/* ===== 所有输入框位置（改 className 即可） ===== */}
        {/* 顶 */}
        <FieldInput
          field="tubeWidth"
          value={values.tubeWidth}
          onChange={onChange}
          placeholder="方管宽度"
          className="left-[67%] top-[10px] -translate-x-1/2"
        />
        <FieldInput
          field="width"
          value={values.width}
          onChange={onChange}
          placeholder="截面宽度"
          className="left-[67%] top-[55px] -translate-x-1/2"
        />

        {/* 左竖直：间距 dimGap=45，输入框在线左侧 */}
        <FieldInput
          field="tubeWidth"
          value={values.tubeWidth}
          onChange={onChange}
          placeholder="方管宽度"
          vertical
          className="left-[-20px] top-[138px]"
        />
        <FieldInput
          field="height"
          value={values.height}
          onChange={onChange}
          placeholder="截面高度"
          vertical
          className="left-[22px] top-[138px]"
        />
        <FieldInput
          field="thickness"
          value={values.thickness}
          onChange={onChange}
          placeholder="板厚"
          vertical
          className="left-[65px] top-[138px]"
        />

        {/* 左下：焊缝高度 */}
        <FieldInput
          field="weld"
          value={values.weld}
          onChange={onChange}
          placeholder="焊缝高度"
          className="left-[52px] top-[255px]"
        />

        {/* 右下：方管厚度 */}
        <FieldInput
          field="tubeThickness"
          value={values.tubeThickness}
          onChange={onChange}
          placeholder="方管厚度"
          className="left-[170px] top-[255px]"
        />
      </div>

      {/* 芯材屈服力核算（公式同 BRB结构核算） */}
      <div className="flex flex-col items-center gap-1 border-t border-gray-200 px-2 py-1.5 text-[13px] text-gray-800">
        <div className="flex flex-nowrap items-center justify-center gap-x-1">
          <span>
            力：{theoreticalFy == null ? '—' : `${theoreticalFy}kN`}
          </span>
          <span>，</span>
          <span className={`font-medium ${deviationClass}`}>
            {deviationPercentage == null ? '—' : `${deviationPercentage}%`}
          </span>
        </div>
        <div className="flex flex-nowrap items-center justify-center gap-x-1">
          <span>强度：</span>
          <input
            type="number"
            title="屈服强度 (MPa)"
            aria-label="屈服强度"
            className={`${baseInputClass} h-[26px] w-[56px] shrink-0`}
            style={{ MozAppearance: 'textfield' } as React.CSSProperties}
            onWheel={(e) => (e.target as HTMLInputElement).blur()}
            onDragStart={(e) => e.stopPropagation()}
            value={yieldStrength}
            onChange={(e) => onYieldStrengthChange?.(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
};

export default WangSectionParams;
