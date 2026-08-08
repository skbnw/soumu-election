/*
 * 衆院選データアーカイブ — DuckDB-Wasm 検索
 * v2.4.2
 * - 起動時の市区町村全件インデックス読込をやめ、プルダウンは都度SQL取得（起動ハング対策）
 * - 比例代表: 政党プルダウン（全国得票順）
 * - 見出し「衆院選データ横断検索β」
 */

import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.30.0/+esm';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  db: null, conn: null, rows: [], ready: false, tab: 'smd',
  electionsByTab: { smd: [], muni: [], pr: [], turnout: [], judicial: [] },
  partiesByElection: {},
  districtsByPref: {},
  muniDistrictsByPref: {},
  allPrefectures: [],
  muniPrefectures: [],
  factCount: 0,
  hasMunicipality: false
};

const els = {
  form: $('#filters'), election: $('#election'), prefecture: $('#prefecture'),
  district: $('#district'), municipality: $('#municipality'),
  contest: $('#contest'), scope: $('#scope'), geoLevel: $('#geo-level'),
  prBlock: $('#pr-block'), prParty: $('#pr-party'), metric: $('#metric'), keyword: $('#keyword'),
  keywordLabel: $('#keyword-label'), search: $('#search'), status: $('#status'),
  results: $('#results'), head: $('#result-head'), download: $('#download'),
  matchCount: $('#match-count'), shownCount: $('#shown-count'),
  resultLabel: $('#result-label'), tabNote: $('#tab-note')
};

const escapeSql = (value) => String(value).replaceAll("'", "''");
const displayNumber = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 3 });
const html = (value) => String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const INIT_TIMEOUT_MS = 60000;
const RESULT_LIMIT = 500;

const ELECTION_YEARS = {
  44: 2005, 45: 2009, 46: 2012, 47: 2014,
  48: 2017, 49: 2021, 50: 2024, 51: 2026
};

const PREFECTURE_ORDER = [
  '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
  '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
  '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
  '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
  '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
  '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
  '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
];
const PREFECTURE_RANK = Object.fromEntries(PREFECTURE_ORDER.map((name, i) => [name, i]));
const PR_BLOCK_ORDER = ['北海道', '東北', '北関東', '南関東', '東京都', '北陸信越', '東海', '近畿', '中国', '四国', '九州', '全国'];
const PR_BLOCK_RANK = Object.fromEntries(PR_BLOCK_ORDER.map((name, i) => [name, i]));

const CONTEST_LABELS = { smd: '小選挙区', pr: '比例代表', judicial_review: '国民審査', all: '全体' };
const SCOPE_LABELS = { all: '全体', overseas: '在外' };
const GENDER_LABELS = { total: '計', male: '男', female: '女' };
const METRIC_LABELS = {
  candidate_votes: '候補者得票', party_votes: '政党得票',
  eligible_voters: '有権者数', voters: '投票者数', turnout_rate: '投票率',
  dismissal_yes: '罷免可', dismissal_no: '罷免不可'
};
const GEO_LEVEL_LABELS = { prefecture: '都道府県', block: 'ブロック', national: '全国' };

const TABS = {
  smd: {
    title: '小選挙区',
    note: '選挙区単位の候補者得票（第44〜51回）。第49回以降は総務省表に性別列がないため性別は空欄です。',
    keywordLabel: '候補者名',
    keywordPlaceholder: '例：道下大樹',
    metrics: [{ value: 'candidate_votes', label: '候補者得票' }],
    fixedContest: 'smd',
    fixedMetric: 'candidate_votes'
  },
  muni: {
    title: '市区町村',
    note: '市区町村を選ぶと、小選挙区・比例代表の開票区別得票に加え、同都道府県の有権者・投票・国民審査（都道府県単位）を一覧します。第45〜51回。並びは区分→市町村名降順です。',
    keywordLabel: '候補者・政党名',
    keywordPlaceholder: '例：道下大樹 / 自由民主党',
    metrics: [{ value: 'candidate_votes', label: '横断一覧' }],
    fixedContest: 'smd',
    fixedMetric: 'candidate_votes'
  },
  pr: {
    title: '比例代表',
    note: '政党は全国得票の多い順です。集計単位で都道府県・ブロック・全国を切り替えられます。',
    keywordLabel: '',
    keywordPlaceholder: '',
    metrics: [{ value: 'party_votes', label: '政党得票' }],
    fixedContest: 'pr',
    fixedMetric: 'party_votes'
  },
  turnout: {
    title: '投票・有権者',
    note: '都道府県単位の有権者数・投票者数・投票率です。既定の集計範囲は「全体」（在外は別選択）です。',
    keywordLabel: '',
    keywordPlaceholder: '',
    metrics: [
      { value: 'eligible_voters', label: '有権者数' },
      { value: 'voters', label: '投票者数' },
      { value: 'turnout_rate', label: '投票率' }
    ],
    fixedContest: null,
    fixedMetric: null
  },
  judicial: {
    title: '国民審査',
    note: '最高裁判所裁判官国民審査の罷免可・罷免不可票です。',
    keywordLabel: '裁判官名',
    keywordPlaceholder: '例：裁判官名',
    metrics: [
      { value: 'dismissal_yes', label: '罷免可' },
      { value: 'dismissal_no', label: '罷免不可' }
    ],
    fixedContest: 'judicial_review',
    fixedMetric: null
  }
};

const electionLabel = (kaiji) => {
  const year = ELECTION_YEARS[kaiji];
  return year == null ? `第${kaiji}回` : `第${kaiji}回-${year}`;
};
const sortPrefectures = (names) => names
  .filter((name) => !['計', '合計', '全国'].includes(name))
  .sort((a, b) => (PREFECTURE_RANK[a] ?? 999) - (PREFECTURE_RANK[b] ?? 999) || a.localeCompare(b, 'ja'));
const districtLabel = (districtNumber) => (
  districtNumber == null || districtNumber === '' ? '—' : `第${districtNumber}区`
);
const contestLabel = (contest) => CONTEST_LABELS[contest] ?? (contest ? String(contest) : '—');
const scopeLabel = (scope) => (scope == null || scope === '' ? '—' : (SCOPE_LABELS[scope] ?? String(scope)));
const genderLabel = (gender) => GENDER_LABELS[gender] ?? (gender ? String(gender) : '—');
const metricLabel = (metric) => METRIC_LABELS[metric] ?? (metric ? String(metric) : '—');
const normalizeBlock = (block) => String(block ?? '').replace(/選挙区$/, '') || '—';
const emptyRow = (cols, message) => `<tr><td colspan="${cols}" class="empty">${message}</td></tr>`;

function prHeaders() {
  const level = els.geoLevel.value;
  if (level === 'national') return ['選挙回次', '政党', '得票', '単位', '出典'];
  if (level === 'block') return ['選挙回次', '比例ブロック', '政党', '得票', '単位', '出典'];
  return ['選挙回次', '比例ブロック', '都道府県', '政党', '得票', '単位', '出典'];
}

function currentHeaders() {
  if (state.tab === 'smd') return ['選挙回次', '都道府県', '選挙区', '候補者', '性別', '得票', '単位', '出典'];
  if (state.tab === 'muni') return ['選挙回次', '区分', '都道府県', '選挙区', '市区町村', '項目', '党派', '値', '単位', '粒度', '出典'];
  if (state.tab === 'pr') return prHeaders();
  if (state.tab === 'turnout') return ['選挙回次', '選挙区分', '集計範囲', '都道府県', '指標', '性別', '値', '単位', '出典'];
  return ['選挙回次', '都道府県', '裁判官', '指標', '値', '単位', '出典'];
}

async function clearLegacyCoiServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  const registrations = await navigator.serviceWorker.getRegistrations();
  const coiRegs = registrations.filter((reg) => {
    const url = reg.active?.scriptURL || reg.waiting?.scriptURL || reg.installing?.scriptURL || '';
    return url.includes('coi-serviceworker');
  });
  if (!coiRegs.length) return;
  await Promise.all(coiRegs.map((reg) => reg.unregister()));
  const keys = await caches.keys();
  await Promise.all(keys.map((key) => caches.delete(key)));
  location.reload();
  await new Promise(() => {});
}

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    promise.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error) => { clearTimeout(timer); reject(error); }
    );
  });
}

async function createDuckDbWorker(mainWorkerUrl) {
  const workerResponse = await fetch(mainWorkerUrl);
  if (!workerResponse.ok) throw new Error(`DuckDB worker fetch failed: ${workerResponse.status}`);
  const workerUrl = URL.createObjectURL(new Blob([await workerResponse.text()], { type: 'text/javascript' }));
  const worker = new Worker(workerUrl);
  worker.addEventListener('error', (event) => console.error('DuckDB worker error', event.message || event));
  return { worker, workerUrl };
}

function setControlsEnabled(enabled) {
  [els.election, els.prefecture, els.district, els.municipality, els.contest, els.scope,
    els.geoLevel, els.prBlock, els.prParty, els.metric, els.keyword, els.search]
    .forEach((el) => { if (el) el.disabled = !enabled; });
  $$('.tab').forEach((tab) => { tab.disabled = !enabled; });
}

function fillSelect(select, options, { keepAll = true, allLabel = 'すべて' } = {}) {
  const current = select.value;
  select.innerHTML = keepAll ? `<option value="">${allLabel}</option>` : '';
  options.forEach(({ value, label }) => select.add(new Option(label, value)));
  if ([...select.options].some((o) => o.value === current)) select.value = current;
  else if (keepAll) select.value = '';
}

function refreshElectionOptions() {
  const elections = state.electionsByTab[state.tab] ?? [];
  fillSelect(els.election, elections.map((v) => ({ value: String(v), label: electionLabel(v) })));
}

function refreshDistrictOptions() {
  const pref = els.prefecture.value;
  const source = state.tab === 'muni' ? state.muniDistrictsByPref : state.districtsByPref;
  let districts = [];
  if (pref && source[pref]) districts = source[pref];
  else districts = [...new Set(Object.values(source).flat())].sort((a, b) => a - b);
  fillSelect(els.district, districts.map((d) => ({ value: String(d), label: `第${d}区` })));
}

async function refreshMunicipalityOptions() {
  if (!els.municipality) return;
  if (!state.hasMunicipality || !state.conn) {
    fillSelect(els.municipality, []);
    return;
  }
  const parts = [`municipality IS NOT NULL`];
  if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
  if (els.prefecture.value) parts.push(`prefecture = '${escapeSql(els.prefecture.value)}'`);
  if (els.district.value) parts.push(`district_number = ${Number(els.district.value)}`);
  try {
    const result = await state.conn.query(`
      SELECT DISTINCT municipality
      FROM read_parquet('municipality_facts.parquet')
      WHERE ${parts.join(' AND ')}
      ORDER BY municipality DESC`);
    const names = result.toArray().map((row) => String(row.toJSON().municipality));
    fillSelect(els.municipality, names.map((name) => ({ value: name, label: name })));
  } catch (error) {
    console.error(error);
    fillSelect(els.municipality, []);
  }
}

function refreshPrefectureOptions() {
  const names = state.tab === 'muni' ? state.muniPrefectures : state.allPrefectures;
  fillSelect(els.prefecture, names.map((v) => ({ value: v, label: v })));
}

function refreshPartyOptions() {
  if (!els.prParty) return;
  const kaiji = els.election.value ? Number(els.election.value) : null;
  let parties = [];
  if (kaiji != null && state.partiesByElection[kaiji]) {
    parties = state.partiesByElection[kaiji];
  } else {
    // 選挙回未指定時は最新回の全国得票順を使う
    const latest = (state.electionsByTab.pr ?? [])[0];
    parties = latest != null ? (state.partiesByElection[latest] ?? []) : [];
  }
  fillSelect(els.prParty, parties.map((name) => ({ value: name, label: name })));
}

function applyTab(tabId, { search = true } = {}) {
  state.tab = tabId;
  const tab = TABS[tabId];
  els.form.dataset.tab = tabId;
  els.keyword.value = '';
  els.district.value = '';
  els.municipality.value = '';
  els.prBlock.value = '';
  if (els.prParty) els.prParty.value = '';
  els.prefecture.value = '';
  if (tabId === 'pr') els.geoLevel.value = 'prefecture';
  if (tabId === 'turnout') els.scope.value = 'all';
  els.form.dataset.geolevel = els.geoLevel.value || 'prefecture';
  $$('.tab').forEach((button) => {
    const active = button.dataset.tab === tabId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  els.tabNote.textContent = tab.note;

  els.metric.innerHTML = tab.metrics.map((m) => `<option value="${m.value}">${m.label}</option>`).join('');
  if (tab.fixedMetric) els.metric.value = tab.fixedMetric;
  if (tab.fixedContest) els.contest.value = tab.fixedContest;
  else els.contest.value = '';

  if (tab.keywordLabel) {
    els.keywordLabel.textContent = tab.keywordLabel;
    els.keyword.placeholder = tab.keywordPlaceholder;
  }

  refreshElectionOptions();
  refreshPrefectureOptions();
  refreshDistrictOptions();
  refreshPartyOptions();
  els.head.innerHTML = currentHeaders().map((h) => (
    h === '得票' || h === '値' ? `<th class="numeric">${h}</th>` : `<th>${h}</th>`
  )).join('');

  const finish = async () => {
    if (tabId === 'muni') await refreshMunicipalityOptions();
    if (search && state.ready) runSearch();
  };
  finish();
}

function commonFilters({ includePref = true, includeDistrict = false, includeMunicipality = false } = {}) {
  const parts = [];
  if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
  if (includePref && els.prefecture.value) parts.push(`prefecture = '${escapeSql(els.prefecture.value)}'`);
  if (includeDistrict && els.district.value) parts.push(`district_number = ${Number(els.district.value)}`);
  if (includeMunicipality && els.municipality.value) {
    parts.push(`municipality = '${escapeSql(els.municipality.value)}'`);
  }
  return parts;
}

function whereClauseSmd() {
  const parts = [
    `metric = 'candidate_votes'`,
    `contest = 'smd'`,
    ...commonFilters({ includePref: true, includeDistrict: true })
  ];
  if (els.keyword.value.trim()) {
    parts.push(`coalesce(candidate, '') ILIKE '%${escapeSql(els.keyword.value.trim())}%'`);
  }
  return parts.join(' AND ');
}

function whereClauseMuniCore() {
  const parts = [...commonFilters({ includePref: true, includeDistrict: false, includeMunicipality: true })];
  // district filter applies only to SMD rows inside the UNION
  if (els.keyword.value.trim()) {
    const q = escapeSql(els.keyword.value.trim());
    parts.push(`(coalesce(subject, '') ILIKE '%${q}%' OR coalesce(party, '') ILIKE '%${q}%' OR coalesce(candidate, '') ILIKE '%${q}%')`);
  }
  return parts.join(' AND ');
}

function whereClauseMuniSmdExtra() {
  return els.district.value ? ` AND district_number = ${Number(els.district.value)}` : '';
}

function whereClausePrefRelated() {
  const parts = [];
  if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
  if (els.prefecture.value) {
    parts.push(`prefecture = '${escapeSql(els.prefecture.value)}'`);
  } else if (els.municipality.value) {
    parts.push(`prefecture IN (
      SELECT DISTINCT prefecture
      FROM read_parquet('municipality_facts.parquet')
      WHERE municipality = '${escapeSql(els.municipality.value)}' AND prefecture IS NOT NULL
    )`);
  }
  return parts.join(' AND ');
}

function whereClauseTurnout() {
  const parts = [`metric = '${escapeSql(els.metric.value)}'`];
  if (els.contest.value) parts.push(`contest = '${escapeSql(els.contest.value)}'`);
  if (els.scope.value === 'all') parts.push(`(scope = 'all' OR scope IS NULL)`);
  else if (els.scope.value) parts.push(`scope = '${escapeSql(els.scope.value)}'`);
  parts.push(...commonFilters({ includePref: true }));
  return parts.join(' AND ');
}

function whereClauseJudicial() {
  const parts = [
    `metric = '${escapeSql(els.metric.value)}'`,
    `contest = 'judicial_review'`,
    ...commonFilters({ includePref: true })
  ];
  if (els.keyword.value.trim()) {
    parts.push(`coalesce(justice, '') ILIKE '%${escapeSql(els.keyword.value.trim())}%'`);
  }
  return parts.join(' AND ');
}

function selectSql() {
  if (state.tab === 'smd') {
    return `SELECT election_kaiji, prefecture, prefecture_code, district_number,
      candidate, gender, value, unit, source_code
      FROM read_parquet('facts.parquet') WHERE ${whereClauseSmd()}
      ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, district_number NULLS LAST, value DESC NULLS LAST
      LIMIT ${RESULT_LIMIT}`;
  }

  if (state.tab === 'muni') {
    const core = whereClauseMuniCore();
    const smdExtra = whereClauseMuniSmdExtra();
    const prefWhere = whereClausePrefRelated();
    const keyword = els.keyword.value.trim();
    const keywordSql = keyword
      ? `AND (coalesce(CAST(metric AS VARCHAR), '') ILIKE '%${escapeSql(keyword)}%' OR coalesce(justice, '') ILIKE '%${escapeSql(keyword)}%')`
      : '';
    // Prefer exact municipality match; if none selected, show municipality-grain rows under filters.
    return `
      WITH muni_rows AS (
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               municipality, subject, party, value, unit, grain, source_code,
               CASE category WHEN '小選挙区' THEN 0 WHEN '比例代表' THEN 1 ELSE 9 END AS category_rank
        FROM read_parquet('municipality_facts.parquet')
        WHERE ${core || '1=1'}
          AND (category = '比例代表' OR (category = '小選挙区'${smdExtra}))
      ),
      pref_turnout AS (
        SELECT election_kaiji,
               '有権者・投票' AS category,
               prefecture,
               prefecture_code,
               NULL::INTEGER AS district_number,
               NULL::VARCHAR AS municipality,
               CASE metric
                 WHEN 'eligible_voters' THEN '有権者数'
                 WHEN 'voters' THEN '投票者数'
                 WHEN 'turnout_rate' THEN '投票率'
                 ELSE CAST(metric AS VARCHAR)
               END AS subject,
               CASE gender WHEN 'male' THEN '男' WHEN 'female' THEN '女' WHEN 'total' THEN '計' ELSE gender END AS party,
               value, unit,
               'prefecture' AS grain,
               source_code,
               2 AS category_rank
        FROM read_parquet('facts.parquet')
        WHERE contest = 'smd'
          AND metric IN ('eligible_voters', 'voters', 'turnout_rate')
          AND (scope = 'all' OR scope IS NULL)
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          ${prefWhere ? `AND ${prefWhere}` : ''}
          ${keywordSql}
          ${els.municipality.value || els.prefecture.value ? '' : 'AND 1=0'}
      ),
      pref_judicial AS (
        SELECT election_kaiji,
               '国民審査' AS category,
               prefecture,
               prefecture_code,
               NULL::INTEGER AS district_number,
               NULL::VARCHAR AS municipality,
               justice AS subject,
               CASE metric WHEN 'dismissal_yes' THEN '罷免可' WHEN 'dismissal_no' THEN '罷免不可' ELSE CAST(metric AS VARCHAR) END AS party,
               value, unit,
               'prefecture' AS grain,
               source_code,
               3 AS category_rank
        FROM read_parquet('facts.parquet')
        WHERE contest = 'judicial_review'
          AND metric IN ('dismissal_yes', 'dismissal_no')
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          ${prefWhere ? `AND ${prefWhere}` : ''}
          ${keywordSql}
          ${els.municipality.value || els.prefecture.value ? '' : 'AND 1=0'}
      )
      SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
             municipality, subject, party, value, unit, grain, source_code
      FROM (
        SELECT * FROM muni_rows
        UNION ALL
        SELECT * FROM pref_turnout
        UNION ALL
        SELECT * FROM pref_judicial
      )
      ORDER BY category_rank,
               municipality DESC NULLS LAST,
               election_kaiji DESC,
               prefecture_code NULLS LAST,
               district_number NULLS LAST,
               value DESC NULLS LAST
      LIMIT ${RESULT_LIMIT}`;
  }

  if (state.tab === 'pr') {
    const level = els.geoLevel.value;
    const partyFilter = els.prParty?.value
      ? `AND party = '${escapeSql(els.prParty.value)}'`
      : '';
    const partyNotTotal = `AND coalesce(party, '') <> '合計'`;
    const electionFilter = els.election.value ? `AND election_kaiji = ${Number(els.election.value)}` : '';
    const blockFilter = els.prBlock.value
      ? `AND replace(pr_block, '選挙区', '') = '${escapeSql(els.prBlock.value)}'`
      : '';
    const prefFilter = els.prefecture.value ? `AND prefecture = '${escapeSql(els.prefecture.value)}'` : '';

    if (level === 'national') {
      return `
        WITH national_direct AS (
          SELECT election_kaiji, party, max(value) AS value,
                 any_value(unit) AS unit, '03-07' AS source_code
          FROM read_parquet('facts.parquet')
          WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-07'
            AND pr_block = '全国' ${partyNotTotal} ${electionFilter} ${partyFilter}
          GROUP BY election_kaiji, party
        ),
        national_from_blocks AS (
          SELECT election_kaiji, party, sum(value) AS value,
                 any_value(unit) AS unit, '集計' AS source_code
          FROM read_parquet('facts.parquet')
          WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
            ${partyNotTotal}
            AND election_kaiji NOT IN (SELECT DISTINCT election_kaiji FROM national_direct)
            ${electionFilter} ${partyFilter}
          GROUP BY election_kaiji, party
        )
        SELECT election_kaiji, '全国' AS pr_block, party, value, unit, source_code
        FROM (
          SELECT * FROM national_direct
          UNION ALL
          SELECT * FROM national_from_blocks
        )
        ORDER BY election_kaiji DESC, value DESC NULLS LAST
        LIMIT ${RESULT_LIMIT}`;
    }

    if (level === 'block') {
      return `
        SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block, party,
               max(value) AS value, any_value(unit) AS unit, any_value(source_code) AS source_code
        FROM read_parquet('facts.parquet')
        WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
          ${electionFilter} ${blockFilter} ${partyNotTotal} ${partyFilter}
        GROUP BY election_kaiji, replace(pr_block, '選挙区', ''), party
        ORDER BY election_kaiji DESC, value DESC NULLS LAST
        LIMIT ${RESULT_LIMIT}`;
    }

    return `
      SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block,
             prefecture, any_value(prefecture_code) AS prefecture_code, party,
             arg_min(value, CAST(regexp_extract(source_cell, '(\\d+)', 1) AS INTEGER)) AS value,
             any_value(unit) AS unit, any_value(source_code) AS source_code
      FROM read_parquet('facts.parquet')
      WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-07'
        AND prefecture IS NOT NULL
        AND prefecture NOT IN ('計', '合計', '全国')
        ${electionFilter} ${blockFilter} ${prefFilter} ${partyNotTotal} ${partyFilter}
      GROUP BY election_kaiji, replace(pr_block, '選挙区', ''), prefecture, party
      ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, value DESC NULLS LAST
      LIMIT ${RESULT_LIMIT}`;
  }

  if (state.tab === 'turnout') {
    return `SELECT election_kaiji, contest, scope, prefecture, prefecture_code,
      metric, gender, value, unit, source_code
      FROM read_parquet('facts.parquet') WHERE ${whereClauseTurnout()}
      ORDER BY election_kaiji DESC, contest NULLS LAST,
               CASE scope WHEN 'all' THEN 0 WHEN 'overseas' THEN 1 ELSE 2 END,
               prefecture_code NULLS LAST,
               CASE gender WHEN 'total' THEN 0 WHEN 'male' THEN 1 WHEN 'female' THEN 2 ELSE 3 END
      LIMIT ${RESULT_LIMIT}`;
  }

  return `SELECT election_kaiji, prefecture, prefecture_code, justice,
    metric, value, unit, source_code
    FROM read_parquet('facts.parquet') WHERE ${whereClauseJudicial()}
    ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, justice NULLS LAST, value DESC NULLS LAST
    LIMIT ${RESULT_LIMIT}`;
}

function countSql() {
  if (state.tab === 'pr') {
    return `SELECT count(*) AS count FROM (${selectSql().replace(new RegExp(` LIMIT ${RESULT_LIMIT}$`), '')})`;
  }
  if (state.tab === 'muni') {
    return `SELECT count(*) AS count FROM (${selectSql().replace(new RegExp(` LIMIT ${RESULT_LIMIT}$`), '')})`;
  }
  const where = state.tab === 'smd' ? whereClauseSmd()
    : state.tab === 'turnout' ? whereClauseTurnout()
      : whereClauseJudicial();
  return `SELECT count(*) AS count FROM read_parquet('facts.parquet') WHERE ${where}`;
}

function renderRows() {
  const headers = currentHeaders();
  if (!state.rows.length) {
    const tip = state.tab === 'muni'
      ? '条件に一致するデータがありません。選挙回・都道府県・選挙区・市区町村を見直してください。'
      : state.tab === 'smd'
        ? '条件に一致するデータがありません。選挙回・都道府県・選挙区の条件を見直してください。'
        : '条件に一致するデータがありません';
    els.results.innerHTML = emptyRow(headers.length, tip);
    return;
  }

  const sorted = [...state.rows];
  if (state.tab === 'pr') {
    sorted.sort((a, b) => {
      if (a.election_kaiji !== b.election_kaiji) return b.election_kaiji - a.election_kaiji;
      const br = (PR_BLOCK_RANK[normalizeBlock(a.pr_block)] ?? 999) - (PR_BLOCK_RANK[normalizeBlock(b.pr_block)] ?? 999);
      if (br) return br;
      const pr = (PREFECTURE_RANK[a.prefecture] ?? 999) - (PREFECTURE_RANK[b.prefecture] ?? 999);
      if (pr) return pr;
      return (b.value ?? 0) - (a.value ?? 0);
    });
  }

  if (state.tab === 'smd') {
    els.results.innerHTML = sorted.map((row) => `<tr>
      <td>${html(electionLabel(row.election_kaiji))}</td>
      <td>${html(row.prefecture)}</td>
      <td>${html(districtLabel(row.district_number))}</td>
      <td>${html(row.candidate)}</td>
      <td>${html(genderLabel(row.gender))}</td>
      <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
      <td>${html(row.unit)}</td>
      <td>${html(row.source_code)}</td></tr>`).join('');
    return;
  }

  if (state.tab === 'muni') {
    const grainLabel = (grain) => (grain === 'prefecture' ? '都道府県' : '市区町村');
    els.results.innerHTML = sorted.map((row) => `<tr>
      <td>${html(electionLabel(row.election_kaiji))}</td>
      <td>${html(row.category)}</td>
      <td>${html(row.prefecture)}</td>
      <td>${html(districtLabel(row.district_number))}</td>
      <td>${html(row.municipality)}</td>
      <td>${html(row.subject)}</td>
      <td>${html(row.party)}</td>
      <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
      <td>${html(row.unit)}</td>
      <td>${html(grainLabel(row.grain))}</td>
      <td>${html(row.source_code)}</td></tr>`).join('');
    return;
  }

  if (state.tab === 'pr') {
    const level = els.geoLevel.value;
    els.results.innerHTML = sorted.map((row) => {
      const block = normalizeBlock(row.pr_block);
      if (level === 'national') {
        return `<tr>
          <td>${html(electionLabel(row.election_kaiji))}</td>
          <td>${html(row.party)}</td>
          <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
          <td>${html(row.unit)}</td>
          <td>${html(row.source_code)}</td></tr>`;
      }
      if (level === 'block') {
        return `<tr>
          <td>${html(electionLabel(row.election_kaiji))}</td>
          <td>${html(block)}</td>
          <td>${html(row.party)}</td>
          <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
          <td>${html(row.unit)}</td>
          <td>${html(row.source_code)}</td></tr>`;
      }
      return `<tr>
        <td>${html(electionLabel(row.election_kaiji))}</td>
        <td>${html(block)}</td>
        <td>${html(row.prefecture)}</td>
        <td>${html(row.party)}</td>
        <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
        <td>${html(row.unit)}</td>
        <td>${html(row.source_code)}</td></tr>`;
    }).join('');
    return;
  }

  if (state.tab === 'turnout') {
    els.results.innerHTML = sorted.map((row) => `<tr>
      <td>${html(electionLabel(row.election_kaiji))}</td>
      <td>${html(contestLabel(row.contest))}</td>
      <td>${html(scopeLabel(row.scope))}</td>
      <td>${html(row.prefecture)}</td>
      <td>${html(metricLabel(row.metric))}</td>
      <td>${html(genderLabel(row.gender))}</td>
      <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
      <td>${html(row.unit)}</td>
      <td>${html(row.source_code)}</td></tr>`).join('');
    return;
  }

  els.results.innerHTML = sorted.map((row) => `<tr>
    <td>${html(electionLabel(row.election_kaiji))}</td>
    <td>${html(row.prefecture)}</td>
    <td>${html(row.justice)}</td>
    <td>${html(metricLabel(row.metric))}</td>
    <td class="numeric">${row.value == null ? '—' : displayNumber.format(row.value)}</td>
    <td>${html(row.unit)}</td>
    <td>${html(row.source_code)}</td></tr>`).join('');
}

function csvRowValues(row) {
  if (state.tab === 'smd') {
    return [row.election_kaiji, ELECTION_YEARS[row.election_kaiji] ?? '', row.prefecture, row.district_number,
      row.candidate, row.gender, genderLabel(row.gender), row.value, row.unit, row.source_code];
  }
  if (state.tab === 'muni') {
    return [row.election_kaiji, ELECTION_YEARS[row.election_kaiji] ?? '', row.category, row.prefecture,
      row.district_number, row.municipality, row.subject, row.party, row.value, row.unit, row.grain, row.source_code];
  }
  if (state.tab === 'pr') {
    return [row.election_kaiji, ELECTION_YEARS[row.election_kaiji] ?? '', els.geoLevel.value,
      normalizeBlock(row.pr_block), row.prefecture, row.party, row.value, row.unit, row.source_code];
  }
  if (state.tab === 'turnout') {
    return [row.election_kaiji, ELECTION_YEARS[row.election_kaiji] ?? '', row.contest, contestLabel(row.contest),
      row.scope, scopeLabel(row.scope), row.prefecture, row.metric, metricLabel(row.metric),
      row.gender, genderLabel(row.gender), row.value, row.unit, row.source_code];
  }
  return [row.election_kaiji, ELECTION_YEARS[row.election_kaiji] ?? '', row.prefecture, row.justice,
    row.metric, metricLabel(row.metric), row.value, row.unit, row.source_code];
}

async function runSearch(event) {
  event?.preventDefault();
  if (!state.ready) return;
  if (state.tab === 'muni' && !state.hasMunicipality) {
    els.results.innerHTML = emptyRow(currentHeaders().length, '市区町村データが読み込まれていません。');
    return;
  }
  const headers = currentHeaders();
  els.head.innerHTML = headers.map((h) => (
    h === '得票' || h === '値' ? `<th class="numeric">${h}</th>` : `<th>${h}</th>`
  )).join('');
  els.form.dataset.geolevel = els.geoLevel.value || 'prefecture';
  els.search.disabled = true;
  els.search.textContent = '検索中…';
  try {
    const [summary, result] = await Promise.all([
      state.conn.query(countSql()),
      state.conn.query(selectSql())
    ]);
    const totals = summary.toArray()[0].toJSON();
    state.rows = result.toArray().map((row) => row.toJSON());
    els.matchCount.textContent = displayNumber.format(Number(totals.count));
    els.shownCount.textContent = displayNumber.format(state.rows.length);
    const tab = TABS[state.tab];
    const metric = tab.fixedMetric || els.metric.value;
    const geo = state.tab === 'pr' ? ` / ${GEO_LEVEL_LABELS[els.geoLevel.value]}` : '';
    els.resultLabel.textContent = `${tab.title}${geo} / ${metricLabel(metric)} — 最大${RESULT_LIMIT}件を表示`;
    els.download.disabled = state.rows.length === 0;
    renderRows();
  } catch (error) {
    console.error(error);
    els.results.innerHTML = emptyRow(headers.length, '検索に失敗しました。条件を変えて再試行してください。');
  } finally {
    els.search.disabled = false;
    els.search.textContent = '検索する';
  }
}

function downloadCsv() {
  const headers = state.tab === 'smd'
    ? ['election_kaiji', 'election_year', 'prefecture', 'district_number', 'candidate', 'gender', 'gender_label', 'value', 'unit', 'source_code']
    : state.tab === 'muni'
      ? ['election_kaiji', 'election_year', 'category', 'prefecture', 'district_number', 'municipality', 'subject', 'party', 'value', 'unit', 'grain', 'source_code']
      : state.tab === 'pr'
        ? ['election_kaiji', 'election_year', 'geo_level', 'pr_block', 'prefecture', 'party', 'value', 'unit', 'source_code']
        : state.tab === 'turnout'
          ? ['election_kaiji', 'election_year', 'contest', 'contest_label', 'scope', 'scope_label', 'prefecture', 'metric', 'metric_label', 'gender', 'gender_label', 'value', 'unit', 'source_code']
          : ['election_kaiji', 'election_year', 'prefecture', 'justice', 'metric', 'metric_label', 'value', 'unit', 'source_code'];
  const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const csv = '\uFEFF' + [headers.join(','), ...state.rows.map((row) => csvRowValues(row).map(quote).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `soumu-election-${state.tab}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

async function loadCoverage() {
  const coverage = await state.conn.query(`
    SELECT
      list_sort(list_distinct(list(election_kaiji) FILTER (WHERE metric = 'candidate_votes' AND contest = 'smd'))) smd_elections,
      list_sort(list_distinct(list(election_kaiji) FILTER (WHERE metric = 'party_votes' AND contest = 'pr'))) pr_elections,
      list_sort(list_distinct(list(election_kaiji) FILTER (WHERE metric IN ('eligible_voters','voters','turnout_rate')))) turnout_elections,
      list_sort(list_distinct(list(election_kaiji) FILTER (WHERE contest = 'judicial_review'))) judicial_elections,
      list_sort(list_distinct(list(prefecture) FILTER (WHERE prefecture IS NOT NULL))) prefectures,
      count(*) AS fact_count
    FROM read_parquet('facts.parquet')`);
  const values = coverage.toArray()[0].toJSON();
  const toNums = (list) => Array.from(list ?? []).map(Number).sort((a, b) => b - a);
  state.electionsByTab.smd = toNums(values.smd_elections);
  state.electionsByTab.pr = toNums(values.pr_elections);
  state.electionsByTab.turnout = toNums(values.turnout_elections);
  state.electionsByTab.judicial = toNums(values.judicial_elections);
  state.allPrefectures = sortPrefectures(Array.from(values.prefectures ?? []).map(String));
  state.factCount = Number(values.fact_count ?? 0);

  const districts = await state.conn.query(`
    SELECT prefecture, list_sort(list_distinct(list(district_number))) districts
    FROM read_parquet('facts.parquet')
    WHERE metric = 'candidate_votes' AND contest = 'smd' AND district_number IS NOT NULL
    GROUP BY prefecture`);
  state.districtsByPref = {};
  for (const row of districts.toArray()) {
    const item = row.toJSON();
    state.districtsByPref[String(item.prefecture)] = Array.from(item.districts ?? []).map(Number);
  }

  if (state.hasMunicipality) {
    const muniMeta = await state.conn.query(`
      SELECT list_sort(list_distinct(list(election_kaiji))) elections,
             list_sort(list_distinct(list(prefecture))) prefectures
      FROM read_parquet('municipality_facts.parquet')
      WHERE prefecture IS NOT NULL`);
    const meta = muniMeta.toArray()[0].toJSON();
    state.electionsByTab.muni = toNums(meta.elections);
    state.muniPrefectures = sortPrefectures(Array.from(meta.prefectures ?? []).map(String));

    const muniDistricts = await state.conn.query(`
      SELECT prefecture, list_sort(list_distinct(list(district_number))) districts
      FROM read_parquet('municipality_facts.parquet')
      WHERE category = '小選挙区' AND district_number IS NOT NULL AND prefecture IS NOT NULL
      GROUP BY prefecture`);
    state.muniDistrictsByPref = {};
    for (const row of muniDistricts.toArray()) {
      const item = row.toJSON();
      state.muniDistrictsByPref[String(item.prefecture)] = Array.from(item.districts ?? []).map(Number);
    }
  } else {
    state.electionsByTab.muni = [];
    state.muniPrefectures = [];
    state.muniDistrictsByPref = {};
  }

  fillSelect(els.prBlock, PR_BLOCK_ORDER.filter((b) => b !== '全国').map((v) => ({ value: v, label: v })));

  // 選挙回ごとの全国得票順政党リスト（比例ブロック得票の合計）
  const partyRows = await state.conn.query(`
    SELECT election_kaiji, party, sum(value) AS votes
    FROM read_parquet('facts.parquet')
    WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
      AND coalesce(party, '') NOT IN ('', '合計')
    GROUP BY election_kaiji, party
    ORDER BY election_kaiji, votes DESC NULLS LAST, party`);
  state.partiesByElection = {};
  for (const row of partyRows.toArray()) {
    const item = row.toJSON();
    const kaiji = Number(item.election_kaiji);
    if (!state.partiesByElection[kaiji]) state.partiesByElection[kaiji] = [];
    state.partiesByElection[kaiji].push(String(item.party));
  }
}

async function init() {
  applyTab('smd', { search: false });
  try {
    await clearLegacyCoiServiceWorker();
    const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
    const { worker, workerUrl } = await createDuckDbWorker(bundle.mainWorker);
    state.db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
    await withTimeout(state.db.instantiate(bundle.mainModule, null), INIT_TIMEOUT_MS, 'DuckDB instantiate');
    URL.revokeObjectURL(workerUrl);

    const factsResponse = await fetch(new URL('./data/facts.parquet', window.location.href).href);
    if (!factsResponse.ok) throw new Error(`データ取得失敗: ${factsResponse.status}`);
    await state.db.registerFileBuffer('facts.parquet', new Uint8Array(await factsResponse.arrayBuffer()));

    const muniResponse = await fetch(new URL('./data/municipality_facts.parquet', window.location.href).href);
    state.hasMunicipality = muniResponse.ok;
    if (state.hasMunicipality) {
      await state.db.registerFileBuffer('municipality_facts.parquet', new Uint8Array(await muniResponse.arrayBuffer()));
    }

    state.conn = await state.db.connect();
    await loadCoverage();

    state.ready = true;
    setControlsEnabled(true);
    els.status.className = 'status ready';
    els.status.innerHTML = `<span class="pulse"></span>${displayNumber.format(state.factCount)}件を読み込み済み`;
    applyTab('smd');
  } catch (error) {
    console.error(error);
    els.status.className = 'status error';
    els.status.innerHTML = '<span class="pulse"></span>読み込みに失敗しました';
    els.results.innerHTML = emptyRow(8, 'データを読み込めませんでした。通信環境を確認して再読み込みしてください。');
  }
}

$$('.tab').forEach((button) => {
  button.addEventListener('click', () => {
    if (!state.ready || button.dataset.tab === state.tab) return;
    applyTab(button.dataset.tab);
  });
});
els.election.addEventListener('change', () => {
  if (state.tab === 'muni') refreshMunicipalityOptions();
  if (state.tab === 'pr') refreshPartyOptions();
});
els.prefecture.addEventListener('change', () => {
  if (state.tab === 'smd' || state.tab === 'muni') {
    refreshDistrictOptions();
    if (state.tab === 'muni') refreshMunicipalityOptions();
  }
});
els.district.addEventListener('change', () => {
  if (state.tab === 'muni') refreshMunicipalityOptions();
});
els.geoLevel.addEventListener('change', () => {
  els.form.dataset.geolevel = els.geoLevel.value;
  if (state.ready && state.tab === 'pr') runSearch();
});
els.prParty?.addEventListener('change', () => {
  if (state.ready && state.tab === 'pr') runSearch();
});
els.form.addEventListener('submit', runSearch);
els.download.addEventListener('click', downloadCsv);
init();
