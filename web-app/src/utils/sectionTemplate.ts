/** 截面类型：新名称 + 旧项目兼容 */

export const SECTION_TEMPLATE_OPTIONS = [
  { value: '王（丨）', label: '王（丨）' },
  { value: '王（工）', label: '王（工）' },
  { value: '十', label: '十' },
] as const;

const LEGACY_TEMPLATE_MAP: Record<string, string> = {
  王一: '王（丨）',
  王工: '王（工）',
  十一: '十',
};

export function normalizeSectionTemplate(template?: string | null): string {
  const t = (template || '').trim();
  if (!t) return '王（丨）';
  return LEGACY_TEMPLATE_MAP[t] || t;
}

export function isShiSectionTemplate(template?: string | null): boolean {
  const t = normalizeSectionTemplate(template);
  return t === '十';
}

export function usesWangSectionDiagram(template?: string | null): boolean {
  const t = normalizeSectionTemplate(template);
  return t === '王（丨）' || t === '王（工）' || t === '十';
}
