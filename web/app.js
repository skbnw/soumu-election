import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.30.0/+esm';

const $ = (selector) => document.querySelector(selector);
const state = { db: null, conn: null, rows: [] };
const els = {
  form: $('#filters'), election: $('#election'), prefecture: $('#prefecture'),
  metric: $('#metric'), keyword: $('#keyword'), search: $('#search'),
  status: $('#status'), results: $('#results'), download: $('#download'),
  matchCount: $('#match-count'), valueTotal: $('#value-total'), shownCount: $('#shown-count'),
  resultLabel: $('#result-label')
};

const escapeSql = (value) => String(value).replaceAll("'", "''");
const displayNumber = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 3 });
const html = (value) => String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const metricLabels = Object.fromEntries([...els.metric.options].map(o => [o.value, o.textContent]));

async function init() {
  try {
    const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
    const workerUrl = URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' }));
    const worker = new Worker(workerUrl);
    state.db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
    await state.db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(workerUrl);
    await state.db.registerFileURL('facts.parquet', './data/facts.parquet', duckdb.DuckDBDataProtocol.HTTP, false);
    state.conn = await state.db.connect();
    const dimensions = await state.conn.query(`
      SELECT list_sort(list_distinct(list(election_kaiji))) elections,
             list_sort(list_distinct(list(prefecture))) FILTER (WHERE prefecture IS NOT NULL) prefectures
      FROM read_parquet('facts.parquet')`);
    const values = dimensions.toArray()[0].toJSON();
    values.elections.reverse().forEach(v => els.election.add(new Option(`第${v}回`, v)));
    values.prefectures.filter(v => !['計','合計'].includes(v)).forEach(v => els.prefecture.add(new Option(v, v)));
    [els.election, els.prefecture, els.metric, els.keyword, els.search].forEach(el => el.disabled = false);
    els.status.className = 'status ready';
    els.status.innerHTML = '<span class="pulse"></span>92,628件を読み込み済み';
    await runSearch();
  } catch (error) {
    console.error(error);
    els.status.className = 'status error';
    els.status.innerHTML = '<span class="pulse"></span>読み込みに失敗しました';
    els.results.innerHTML = '<tr><td colspan="8" class="empty">データを読み込めませんでした。通信環境を確認して再読み込みしてください。</td></tr>';
  }
}

function whereClause() {
  const parts = [`metric = '${escapeSql(els.metric.value)}'`];
  if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
  if (els.prefecture.value) parts.push(`prefecture = '${escapeSql(els.prefecture.value)}'`);
  if (els.keyword.value.trim()) {
    const q = escapeSql(els.keyword.value.trim());
    parts.push(`coalesce(candidate, party, justice, '') ILIKE '%${q}%'`);
  }
  return parts.join(' AND ');
}

async function runSearch(event) {
  event?.preventDefault();
  els.search.disabled = true;
  els.search.textContent = '検索中…';
  try {
    const where = whereClause();
    const [summary, result] = await Promise.all([
      state.conn.query(`SELECT count(*) count, sum(value) total FROM read_parquet('facts.parquet') WHERE ${where}`),
      state.conn.query(`SELECT election_kaiji, prefecture, district_number,
        coalesce(candidate, party, justice, '—') label, gender, value, unit, source_code
        FROM read_parquet('facts.parquet') WHERE ${where}
        ORDER BY election_kaiji DESC, prefecture NULLS LAST, district_number NULLS LAST, value DESC NULLS LAST LIMIT 500`)
    ]);
    const totals = summary.toArray()[0].toJSON();
    state.rows = result.toArray().map(row => row.toJSON());
    els.matchCount.textContent = displayNumber.format(totals.count);
    els.valueTotal.textContent = totals.total == null ? '—' : displayNumber.format(totals.total);
    els.shownCount.textContent = displayNumber.format(state.rows.length);
    els.resultLabel.textContent = `${metricLabels[els.metric.value]} — 最大500件を表示`;
    els.download.disabled = state.rows.length === 0;
    renderRows();
  } finally {
    els.search.disabled = false;
    els.search.textContent = '検索する';
  }
}

function renderRows() {
  if (!state.rows.length) {
    els.results.innerHTML = '<tr><td colspan="8" class="empty">条件に一致するデータがありません</td></tr>';
    return;
  }
  els.results.innerHTML = state.rows.map(row => `<tr>
    <td>第${html(row.election_kaiji)}回</td><td>${html(row.prefecture)}</td>
    <td>${row.district_number == null ? '—' : `${html(row.district_number)}区`}</td>
    <td>${html(row.label)}</td><td>${html(row.gender)}</td>
    <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
    <td>${html(row.unit)}</td><td>${html(row.source_code)}</td></tr>`).join('');
}

function downloadCsv() {
  const headers = ['election_kaiji','prefecture','district_number','label','gender','value','unit','source_code'];
  const quote = value => `"${String(value ?? '').replaceAll('"','""')}"`;
  const csv = '\uFEFF' + [headers.join(','), ...state.rows.map(row => headers.map(k => quote(row[k])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url; a.download = `soumu-election-${els.metric.value}.csv`; a.click();
  URL.revokeObjectURL(url);
}

els.form.addEventListener('submit', runSearch);
els.download.addEventListener('click', downloadCsv);
init();
