export const escapeSql = (value) => String(value).replaceAll("'", "''");

export const displayNumber = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 3 });
const displayVotes = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 0 });

/** 総務省Excelの得票に小数が残る場合があるため、票は四捨五入して表示する */
export function formatValue(value, unit) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  if (unit === 'votes' || unit === 'people') return displayVotes.format(Math.round(n));
  return displayNumber.format(n);
}

const displayPercent = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export function formatPercent(value) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${displayPercent.format(n)}%`;
}

/**
 * 開票区つき市区町村名の表記ゆれを揃える。
 * 例: 青森市-1 / 青森市1区 → 青森市（1区）
 * 原文の行政名は変えず、分割開票区の接尾だけを統一する。
 */
export function normalizeMunicipalityLabel(name) {
  const s = String(name || '').trim();
  if (!s) return s;
  let m = s.match(/^(.+)-(\d+)$/);
  if (m) return `${m[1]}（${m[2]}区）`;
  m = s.match(/^(.+?[市町村])(\d+)区$/);
  if (m) return `${m[1]}（${m[2]}区）`;
  return s;
}

/** DuckDB: municipality 列（または式）を表示用ラベルへ */
export function municipalityNormSql(expr) {
  return `CASE
    WHEN regexp_matches(${expr}, '^.+-\\d+$')
      THEN regexp_replace(${expr}, '^(.+)-(\\d+)$', '\\1（\\2区）')
    WHEN regexp_matches(${expr}, '^.+[市町村]\\d+区$')
      THEN regexp_replace(${expr}, '^(.+[市町村])(\\d+)区$', '\\1（\\2区）')
    ELSE ${expr}
  END`;
}

/** 惜敗率。当選（≈100%）は「━」 */
export function formatSekihai(value, elected) {
  if (elected === true || elected === 'true') return '━';
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  if (n >= 99.95) return '━';
  return formatPercent(n);
}
