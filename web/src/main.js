// @ts-check
/*
 * 国政選データ横断検索β — DuckDB-Wasm 検索
 * v2.10.9
 * - 政治学会・小選挙区の絶対得票率を有権者数から再計算（42–45回の割合スケール混在を回避）
 * - 市区町村名の開票区表記を「市（N区）」に正規化（市-N / 市N区 / 市（N区）の混在解消）
 * v2.10.8
 * - 小選挙区／参院県区の相対得票率を、当落・キーワード適用前の全区得票で計算
 * v2.10.7
 * - 政党名の外側括弧（無所属）等を表示・フィルタで除去
 * - 小選挙区／比例などタブ選択を衆院・参院と同様の黒反転に
 * v2.10.6
 * - 小選挙区に政党フィルタ（当落との併用可）。相対得票率は全区得票を分母に計算してから絞る
 * - 比例の相対得票率が政党フィルタ後に100%になる不具合を修正（分母は全区／全市／全市政党）
 * - 選挙回ラベルの数字を半角＋tabular-numsで桁揃え
 * - 市区町村プルダウンを市→区→町→村、日本語ロケール順に
 * v2.10.5
 * - 参院候補者名を読売CD表記で表示（sangiin_yomi_name_map）
 * - 参院タブでも出典列を表示
 * v2.10.4
 * - データソースのユーザー選択を保持し、既定は常に「01 統合」へ復帰
 * - 出典ラベルに読売CD-ROM（参24・26県区）を追加
 * v2.10.3
 * - 比例の政党フィルタを CASE 展開に変更（Wasm 相関サブクエリ回避）
 * - 比例ブロック／全国の結果ソートで BigInt 減算エラーを修正
 * v2.10.2
 * - 政党名別名マップ（MIC正式名↔政治学会略称）を比例フィルタ・表示に接続
 * v2.10.1
 * - データソース表記を 01統合 / 02総務省 / 03政治学会 に整理
 * - 統合・比例の検索失敗を修正（MICブロックは03-10、UNION明示列）
 * v2.10.0
 * - データソース既定を「統合（総務省優先＋政治学会穴埋め）」に変更
 * - 政治学会かなを読売漢字リストで表示（seiji_candidate_name_map）
 * - SH-HD 比例市区町村・turnout の選挙区/市町村粒を統合時に穴埋め
 * v2.9.25
 * - 比例「政党=すべて」検索を安定化（政治学会はブロック/全国に正規化）
 * - 政治学会の投票・有権者／比例代表をデータソース切替で接続
 * - 政治学会選択時の選挙回表示を「1996-衆」形式に
 * - 読売比例名簿を衆41回（1996）以降まで拡張
 * - 衆41〜43回の選挙年・首相ラベルを追加（例: 1996-衆41回-橋本）
 * - 衆院小選挙区／市町村に政治学会（二次）データソース切替を追加（MIC正本は既定）
 * - CSV保存を復活（検索条件に合う全件＋出典）
 * - タブ／議院切替では自動検索せず、空状態のまま「検索する」待ち
 * - 衆院比例名簿の当落を比当／小当／落に分離、出典列を表示
 * - 人名複数表記（読売正本・giin_cd・国会議員白書・MIC異体字/IVS）で検索・表示
 * - 参院も「市町村（詳細）」、県区に当落フィルタ、参院比例名簿タブ
 * - 衆院「市区町村」タブラベルを「市町村（詳細）」へ
 * - 衆院比例名簿を読売紙面名簿（references記事パース）に接続
 * - 衆院比例名簿を読売紙面名簿（当落・氏名）に切替、政党プルダウンの「すべて」を全回合算
 * - 衆院「比例名簿」タブ（03-11名簿順位＋政党当選枠・当落目安）
 * - サイト名を「国政選データ横断検索β」へ
 * - 参院県区に関西大選挙区（21–23都道府県集計）を追加
 * - 結果表の背景帯：選挙回が混在なら選挙回、同一なら選挙区等で区分
 * - 惜敗率100%（当選）を「━」表示、相対/絶対得票率を拡張
 * - 参院県区に当落・相対・絶対得票率、第25回03-13を追加
 * - 選挙回ラベルに選挙時の首相名を付与（例: 2026-衆51回-高市）
 * - 参22のMIC未接続9県を関西大・参院選DBで補完
 * - 参21市区町村全面・参22広島を関西大・参院選DB（二次ソース）で補完
 * - 参院第21回（2007）を接続
 * - 参院第22回（2010）を接続
 * - 参院第23回（2013）を接続
 * - 参院第24回（2016）を接続
 * - 起動失敗時にエラー詳細を表示、市区町村読込失敗でも全国集計を継続
 * - DuckDB初期化タイムアウトを延長
 * - 衆院小選挙区に当落・党派・相対得票率・惜敗率を表示
 * - 参院第25回（2019）を接続
 * - 市区町村名の選挙区接尾辞を統一（全角括弧＋半角数字）
 * - CSV保存を復活（検索条件に合う全件＋出典）
 * - 参院第26回＋市区町村別得票を接続（選挙区／比例政党／名簿候補）
 * - 参院比例「名簿候補」個人名得票、件数表示を目立たなく
 * - 参院県区に定数（1人区等）を表示・絞り込み
 * - 参院: 選挙区候補者（03-13）・比例都道府県党派（03-05）をUI接続
 * - 参院第27回を倉庫に接続（投票・比例の全国／都道府県）
 * - election_id で衆院/参院を分離フィルタ
 * - サイト名変更、衆院/参院チャンバー切替
 * - 選挙表記を「2026-衆51回」形式へ（参院は「2025-参27回」）
 * - 更新日時の表示を強化（meta / manifest フォールバック、HTML初期値）
 * - 人名表示は漢字を基本（かなは candidate_raw 経由で検索ヒット）
 * - 結果のページ送り（1ページ件数 × 前後移動）
 * - 人名/党派名の空白ゆれを除去し、かな＋漢字を併記表示
 * - 結果表から出典列を非表示
 * - 表示件数上限（50/100/200/500）とヘッダ更新日時
 * - 「検索」見出し削除、比例全国は03-05今回得票、票表示は四捨五入
 * - ヒーロー見出しを削り、ヘッダ表記を統一
 * - 起動時の市区町村全件インデックス読込をやめ、プルダウンは都度SQL取得（起動ハング対策）
 * - 比例代表: 政党プルダウン（全国得票順）
 */

import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.30.0/+esm';
import {
  escapeSql, formatValue, formatPercent,
  normalizeMunicipalityLabel, municipalityNormSql, formatSekihai,
  displayNumber
} from './utils.js';


const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  db: null, conn: null, rows: [], ready: false, tab: 'smd',
  chamber: 'shugiin',
  page: 1,
  matchTotal: 0,
  electionsByTab: { smd: [], muni: [], pr: [], prlist: [], turnout: [], judicial: [] },
  partiesByElection: {},
  districtsByPref: {},
  muniDistrictsByPref: {},
  allPrefectures: [],
  muniPrefectures: [],
  factCount: 0,
  hasMunicipality: false,
  hasYomiPrMeibo: false,
  hasPersonAliases: false,
  hasSeijiSmdDistrict: false,
  hasSeijiSmdMuni: false,
  hasSeijiTurnout: false,
  hasSeijiPr: false,
  hasSeijiPrMuni: false,
  hasSeijiNameMap: false,
  hasSangiinYomiNameMap: false,
  hasPartyAliases: false,
  partyAliasGlobal: {},
  partyAliasByKaiji: {},
  seijiDistrictsByPref: {},
  seijiMuniDistrictsByPref: {},
  seijiPrefectures: [],
  seijiMuniPrefectures: [],
  seijiTurnoutPrefectures: [],
  seijiPrBlocks: [],
  seijiSmdElections: [],
  seijiMuniElections: [],
  seijiTurnoutElections: [],
  seijiPrElections: [],
  partiesByElectionSeiji: {},
  partiesByElectionSmd: {},
  partiesByElectionSeijiSmd: {},
  /** ユーザーが選んだデータソース（政治学会非対応タブでは一時的に mic 表示しても保持） */
  dataSourcePreference: 'unified'
};

const els = {
  form: $('#filters'), election: $('#election'), prefecture: $('#prefecture'),
  district: $('#district'), municipality: $('#municipality'),
  contest: $('#contest'), scope: $('#scope'), geoLevel: $('#geo-level'),
  prBlock: $('#pr-block'), prParty: $('#pr-party'), metric: $('#metric'), keyword: $('#keyword'),
  electedFilter: $('#elected-filter'), dataSource: $('#data-source'), gender: $('#gender'),
  keywordLabel: $('#keyword-label'), search: $('#search'), status: $('#status'),
  results: $('#results'), head: $('#result-head'), download: $('#download'),
  resultRange: $('#result-range'),
  resultLabel: $('#result-label'), tabNote: $('#tab-note'),
  resultLimit: $('#result-limit'), updatedAt: $('#updated-at'),
  pager: $('#pager'), pagePrev: $('#page-prev'), pageNext: $('#page-next'),
  pageStatus: $('#page-status'), tableShell: $('.table-shell'),
  chamberShugiin: $('#chamber-panel-shugiin'),
  chamberSangiin: $('#chamber-panel-sangiin')
};

// Utilities imported from utils.js

function municipalityFilterSql(expr = 'municipality') {
  if (!els.municipality?.value) return null;
  const want = normalizeMunicipalityLabel(els.municipality.value);
  return `${municipalityNormSql(expr)} = '${escapeSql(want)}'`;
}


function canUseSeijiForTab() {
  if (state.chamber !== 'shugiin') return false;
  if (state.tab === 'smd') return state.hasSeijiSmdDistrict;
  if (state.tab === 'muni') return state.hasSeijiSmdMuni || state.hasSeijiPrMuni;
  if (state.tab === 'turnout') return state.hasSeijiTurnout;
  if (state.tab === 'pr') return state.hasSeijiPr;
  return false;
}

/** unified | mic | seiji-gakkai */
function dataSourceMode() {
  if (state.chamber !== 'shugiin' || !canUseSeijiForTab()) return 'mic';
  const v = els.dataSource?.value || 'unified';
  if (v === 'seiji-gakkai' || v === 'mic' || v === 'unified') return v;
  return 'unified';
}

function usesSeijiSource() {
  return dataSourceMode() === 'seiji-gakkai';
}

function usesUnifiedSource() {
  return dataSourceMode() === 'unified' && canUseSeijiForTab();
}

function showsSourceColumn() {
  if (state.chamber === 'sangiin') {
    return ['smd', 'muni', 'pr', 'prlist', 'turnout'].includes(state.tab);
  }
  return usesSeijiSource() || usesUnifiedSource();
}

/** 政治学会選択時も年付き＋首相（例: 1996-衆41回-橋本）。 */
function electionLabelForUi(kaiji, chamber = state.chamber) {
  return electionLabel(kaiji, chamber);
}

function partyCanonicalSqlExpr(column = 'party', kaijiColumn = 'election_kaiji') {
  if (!state.hasPartyAliases) return column;

  // 回別 override
  const byKaiji = {};
  for (const [key, canon] of Object.entries(state.partyAliasByKaiji || {})) {
    const split = key.indexOf('|');
    if (split < 0) continue;
    const k = key.slice(0, split);
    const alias = key.slice(split + 1);
    if (!byKaiji[k]) byKaiji[k] = [];
    byKaiji[k].push([alias, canon]);
  }
  let kaijiCase = 'NULL';
  const kaijiKeys = Object.keys(byKaiji);
  if (kaijiKeys.length) {
    const whens = kaijiKeys.map((k) => {
      const inner = byKaiji[k]
        .map(([alias, canon]) => `WHEN '${escapeSql(alias)}' THEN '${escapeSql(canon)}'`)
        .join(' ');
      return `WHEN ${Number(k)} THEN (CASE ${column} ${inner} ELSE NULL END)`;
    }).join(' ');
    kaijiCase = `CASE ${kaijiColumn} ${whens} ELSE NULL END`;
  }

  const globalEntries = Object.entries(state.partyAliasGlobal || {});
  const globalCase = globalEntries.length
    ? `(CASE ${column} ${globalEntries
      .map(([alias, canon]) => `WHEN '${escapeSql(alias)}' THEN '${escapeSql(canon)}'`)
      .join(' ')} ELSE NULL END)`
    : 'NULL';

  return `coalesce(${kaijiCase}, ${globalCase}, ${column})`;
}

function stripOuterPartyParens(value) {
  let s = String(value ?? '').trim();
  if (!s) return '';
  // 全体が（…）/ (...) で囲まれているケースを外す（例: （無所属）→無所属）
  for (let i = 0; i < 3; i += 1) {
    if ((s.startsWith('（') && s.endsWith('）')) || (s.startsWith('(') && s.endsWith(')'))) {
      s = s.slice(1, -1).trim();
      continue;
    }
    break;
  }
  if (s.startsWith('（') || s.startsWith('(')) s = s.slice(1).trim();
  if (s.endsWith('）') || s.endsWith(')')) s = s.slice(0, -1).trim();
  return s;
}

function partyFilterSql(column = 'party', kaijiColumn = 'election_kaiji') {
  const raw = stripOuterPartyParens(String(els.prParty?.value ?? '').trim());
  if (!raw || raw === 'すべて') return '';
  const esc = escapeSql(raw);
  const baseExpr = state.hasPartyAliases
    ? partyCanonicalSqlExpr(column, kaijiColumn)
    : column;
  // 表示は括弧なし。データ側の（無所属）等も同一視する
  const stripped = `regexp_replace(regexp_replace(CAST(${baseExpr} AS VARCHAR), '^[（(]+', ''), '[）)]+$', '')`;
  return `AND ${stripped} = '${esc}'`;
}

function canonicalPartyName(party, kaiji = null) {
  const name = stripOuterPartyParens(String(party ?? '').trim());
  if (!name) return '';
  if (!state.hasPartyAliases) return name;
  // 別名表は括弧付きキーの可能性があるため両方見る
  const wrapped = `（${name}）`;
  if (kaiji != null && kaiji !== '') {
    const k = Number(kaiji);
    const keyed = state.partyAliasByKaiji[`${k}|${name}`]
      || state.partyAliasByKaiji[`${k}|${wrapped}`]
      || state.partyAliasByKaiji[`${k}|(${name})`];
    if (keyed) return stripOuterPartyParens(keyed);
  }
  const global = state.partyAliasGlobal[name]
    || state.partyAliasGlobal[wrapped]
    || state.partyAliasGlobal[`(${name})`];
  return stripOuterPartyParens(global || name);
}

function displayPartyName(party, kaiji = null) {
  const canon = canonicalPartyName(party, kaiji);
  return canon ? displayLabel(canon) : '—';
}

function normalizeSeijiPrGeoLevel() {
  if (!(state.tab === 'pr' && usesSeijiSource() && els.geoLevel)) return;
  if (els.geoLevel.value !== 'national' && els.geoLevel.value !== 'block') {
    els.geoLevel.value = 'block';
  }
  els.form.dataset.geolevel = els.geoLevel.value || 'block';
}

function seijiNameMapJoinSql(alias = 's') {
  if (!state.hasSeijiNameMap) return '';
  return `LEFT JOIN read_parquet('seiji_candidate_name_map.parquet') nm
    ON nm.election_kaiji = ${alias}.election_kaiji
    AND nm.prefecture = ${alias}.prefecture
    AND nm.district_number = ${alias}.district_number
    AND nm.vote = ${alias}.value
    AND nm.kana = ${alias}.candidate`;
}

function seijiMuniNameMapJoinSql(alias = 's') {
  if (!state.hasSeijiNameMap) return '';
  return `LEFT JOIN read_parquet('seiji_candidate_name_map.parquet') nm
    ON nm.election_kaiji = ${alias}.election_kaiji
    AND nm.prefecture = ${alias}.prefecture
    AND nm.district_number = ${alias}.district_number
    AND nm.kana = ${alias}.candidate`;
}

function seijiDisplayCandidateSql(alias = 's') {
  return state.hasSeijiNameMap
    ? `coalesce(nm.kanji, ${alias}.candidate)`
    : `${alias}.candidate`;
}

/** 参院・読売CD名マップ（県計） */
function sangiinYomiPrefJoinSql(alias = 'f') {
  if (!state.hasSangiinYomiNameMap) return '';
  return `LEFT JOIN read_parquet('sangiin_yomi_name_map.parquet') ym
    ON ym.grain = 'prefecture'
    AND ym.election_kaiji = ${alias}.election_kaiji
    AND ym.prefecture = ${alias}.prefecture
    AND ym.vote = CAST(${alias}.value AS BIGINT)`;
}

/** 参院・読売CD名マップ（市区町村） */
function sangiinYomiMuniJoinSql(alias = 'm') {
  if (!state.hasSangiinYomiNameMap) return '';
  return `LEFT JOIN read_parquet('sangiin_yomi_name_map.parquet') ym
    ON ym.grain = 'municipality'
    AND ym.election_kaiji = ${alias}.election_kaiji
    AND ym.prefecture = ${alias}.prefecture
    AND ym.municipality = ${alias}.municipality
    AND ym.vote = CAST(${alias}.value AS BIGINT)`;
}

function displayNameFromRow(row) {
  return displayPersonName(
    row.candidate ?? row.subject,
    row.candidate_raw,
    row.yomi_name || row.canonical_name
  );
}

function dualCandidacyLabel(value) {
  if (value === true || value === 'true') return 'あり';
  if (value === false || value === 'false') return 'なし';
  return '—';
}

function syncDataSourceUi() {
  const sourceWrap = els.dataSource?.closest('label') || document.getElementById('data-source-label');
  const canSeiji = canUseSeijiForTab();
  if (sourceWrap) sourceWrap.hidden = !canSeiji;
  if (els.dataSource) {
    if (!canSeiji) {
      // 参院・国民審査など政治学会非対応時は表示のみ総務省（選択は保持）
      els.dataSource.value = 'mic';
    } else {
      const pref = state.dataSourcePreference;
      els.dataSource.value = ['unified', 'mic', 'seiji-gakkai'].includes(pref) ? pref : 'unified';
    }
  }

  const electedWrap = els.electedFilter?.closest('label') || document.getElementById('elected-label');
  if (electedWrap) {
    if (state.tab === 'smd' || state.tab === 'prlist') {
      electedWrap.hidden = false;
    }
  }

  // 政治学会のみ比例に都道府県粒はない → ブロック／全国のみ
  if (els.geoLevel && state.tab === 'pr') {
    const prefOpt = [...els.geoLevel.options].find((o) => o.value === 'prefecture');
    const listOpt = [...els.geoLevel.options].find((o) => o.value === 'list');
    if (usesSeijiSource()) {
      if (prefOpt) prefOpt.hidden = true;
      if (listOpt) listOpt.hidden = true;
      if (els.geoLevel.value === 'prefecture' || els.geoLevel.value === 'list') {
        els.geoLevel.value = 'block';
      }
    } else if (state.chamber === 'shugiin') {
      if (prefOpt) prefOpt.hidden = false;
      if (listOpt) listOpt.hidden = true;
    }
  }

  // 政治学会の投票は在外なし
  if (els.scope && state.tab === 'turnout' && usesSeijiSource()) {
    if (els.scope.value === 'overseas') els.scope.value = 'all';
    [...els.scope.options].forEach((o) => {
      if (o.value === 'overseas') o.hidden = true;
    });
  } else if (els.scope && state.tab === 'turnout') {
    [...els.scope.options].forEach((o) => { o.hidden = false; });
  }

  if (els.gender && state.tab === 'turnout') {
    [...els.gender.options].forEach((o) => { o.hidden = false; o.disabled = false; });
  }
}

function electedLabel(elected) {
  if (elected === true || elected === 'true') return '当選';
  if (elected === false || elected === 'false') return '落選';
  return '—';
}

/** 比例名簿の当落表示（読売紙面） */
function prListOutcomeLabel(outcome) {
  if (outcome === 'smd') return '小当';
  if (outcome === 'pr') return '比当';
  if (outcome === 'loss') return '落';
  return outcome == null || outcome === '' ? '—' : String(outcome);
}

/** 出典コードの画面表示 */
function sourceLabel(source) {
  if (source == null || source === '') return '—';
  const s = String(source);
  if (s === 'yomi_print_article') return '読売紙面記事';
  if (s === 'print_hitou_crossfill' || s.startsWith('print_clean_csv')) return '読売紙面（比当突合）';
  if (s.startsWith('kansai-')) return `関西大DB (${s})`;
  if (s.startsWith('yomi-cdrom-')) return `読売CD-ROM (${s})`;
  if (s.startsWith('seiji-gakkai-')) return `政治学会 (${s})`;
  if (s.startsWith('mic-') || s.startsWith('soumu-')) return `総務省 (${s})`;
  return s;
}

/** 当落フィルタ選択肢（衆院比例名簿は比当／小当／落） */
function refreshElectedFilterOptions() {
  if (!els.electedFilter) return;
  const prev = els.electedFilter.value;
  const usePrlistOutcome = state.tab === 'prlist' && state.chamber === 'shugiin';
  const useSeijiSmd = state.tab === 'smd' && usesSeijiSource();
  const options = usePrlistOutcome
    ? [
      ['', 'すべて'],
      ['pr', '比当'],
      ['smd', '小当'],
      ['loss', '落']
    ]
    : useSeijiSmd
      ? [
        ['', 'すべて'],
        ['smd', '当選（小）'],
        ['pr', '比例復活'],
        ['loss', '落選']
      ]
    : [
      ['', 'すべて'],
      ['won', '当選'],
      ['lost', '落選']
    ];
  els.electedFilter.innerHTML = options
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join('');
  const allowed = new Set(options.map(([value]) => value));
  els.electedFilter.value = allowed.has(prev) ? prev : '';
}

/** 氏名・党派名の文字間空白を除去 */
function stripSpaces(value) {
  return String(value ?? '').replace(/[\s\u3000]+/g, '');
}

/** IVS・異体字セレクタを除いた表示用圧縮 */
function stripNameNoise(value) {
  return String(value ?? '')
    .replace(/[\uFE00-\uFE0F]/gu, '')
    .replace(/[\u{E0100}-\u{E01EF}]/gu, '')
    .replace(/[\s\u3000]+/g, '');
}

/**
 * 表示用の人名は読売正本（canonical_name）を優先。
 * なければ漢字を基本とし、かなは candidate_raw 経由で検索ヒットする。
 */
function displayPersonName(name, raw, canonical) {
  const canon = stripNameNoise(canonical);
  if (canon) return canon;
  const compactName = stripNameNoise(name);
  const withoutPua = compactName.replace(/[\uE000-\uF8FF]/g, '');
  const hasPua = withoutPua !== compactName;
  if (compactName && !hasPua) return compactName;
  if (!raw) return withoutPua || compactName || '—';
  const paren = String(raw).match(/[（(]\s*([^）)]+?)\s*[）)]/);
  if (paren) {
    const kanji = stripNameNoise(paren[1]).replace(/[\uE000-\uF8FF]/g, '');
    if (kanji) return kanji;
  }
  return withoutPua || stripNameNoise(raw) || compactName || '—';
}

function displayLabel(value) {
  const compact = stripSpaces(value);
  return compact || '—';
}

function keywordCompactSql(column) {
  const q = stripSpaces(els.keyword.value);
  if (!q) return '';
  return `replace(replace(coalesce(CAST(${column} AS VARCHAR), ''), ' ', ''), chr(12288), '') ILIKE '%${escapeSql(q)}%'`;
}

/** 読売正本・別名テーブルでキーワードを人物展開する条件 */
function keywordPersonAliasSql(candidateCol = 'candidate', rawCol = 'candidate_raw') {
  if (!state.hasPersonAliases) return '';
  const q = stripSpaces(els.keyword.value);
  if (!q) return '';
  const eq = escapeSql(q);
  return `(
    coalesce(CAST(${candidateCol} AS VARCHAR), '') IN (
      SELECT alias_name FROM read_parquet('person_name_aliases.parquet')
      WHERE person_id IN (
        SELECT DISTINCT person_id FROM read_parquet('person_name_aliases.parquet')
        WHERE alias_normalized ILIKE '%${eq}%'
           OR alias_name ILIKE '%${eq}%'
           OR canonical_name ILIKE '%${eq}%'
           OR coalesce(alias_normalized_soft, '') ILIKE '%${eq}%'
      )
    )
    OR replace(replace(coalesce(CAST(${candidateCol} AS VARCHAR), ''), ' ', ''), chr(12288), '') IN (
      SELECT alias_normalized FROM read_parquet('person_name_aliases.parquet')
      WHERE person_id IN (
        SELECT DISTINCT person_id FROM read_parquet('person_name_aliases.parquet')
        WHERE alias_normalized ILIKE '%${eq}%'
           OR alias_name ILIKE '%${eq}%'
           OR canonical_name ILIKE '%${eq}%'
           OR coalesce(alias_normalized_soft, '') ILIKE '%${eq}%'
      )
      AND coalesce(alias_normalized, '') <> ''
    )
    OR replace(replace(coalesce(CAST(${rawCol} AS VARCHAR), ''), ' ', ''), chr(12288), '') ILIKE '%${eq}%'
  )`;
}

function personCanonicalJoinSql(candidateExpr = 'candidate') {
  if (!state.hasPersonAliases) {
    return `NULL::VARCHAR AS canonical_name, NULL::VARCHAR AS person_id`;
  }
  // 同一 alias が複数人物に付いている場合、候補名＝正本名の人物を優先
  return `(
    SELECT canonical_name FROM (
      SELECT a.canonical_name,
             CASE WHEN a.canonical_name = ${candidateExpr} THEN 0 ELSE 1 END AS pri
      FROM read_parquet('person_name_aliases.parquet') a
      WHERE a.alias_name = ${candidateExpr}
         OR a.alias_normalized = replace(replace(coalesce(CAST(${candidateExpr} AS VARCHAR), ''), ' ', ''), chr(12288), '')
      ORDER BY pri, a.person_id
      LIMIT 1
    )
  ) AS canonical_name,
  (
    SELECT person_id FROM (
      SELECT a.person_id,
             CASE WHEN a.canonical_name = ${candidateExpr} THEN 0 ELSE 1 END AS pri
      FROM read_parquet('person_name_aliases.parquet') a
      WHERE a.alias_name = ${candidateExpr}
         OR a.alias_normalized = replace(replace(coalesce(CAST(${candidateExpr} AS VARCHAR), ''), ' ', ''), chr(12288), '')
      ORDER BY pri, a.person_id
      LIMIT 1
    )
  ) AS person_id`;
}
const html = (value) => String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const INIT_TIMEOUT_MS = 120000;

function resultLimit() {
  const n = Number(els.resultLimit?.value || 100);
  return Number.isFinite(n) && n > 0 ? n : 100;
}

function pageOffset() {
  return Math.max(0, (Number(state.page) - 1) * resultLimit());
}

function pageCount(total = state.matchTotal) {
  return Math.max(1, Math.ceil(Math.max(0, Number(total) || 0) / resultLimit()));
}

function limitOffsetSql() {
  return `LIMIT ${resultLimit()} OFFSET ${pageOffset()}`;
}

function updatePager() {
  if (!els.pager) return;
  const total = Number(state.matchTotal) || 0;
  const pages = pageCount(total);
  if (state.page > pages) state.page = pages;
  if (state.page < 1) state.page = 1;
  const limit = resultLimit();
  const start = total === 0 ? 0 : (state.page - 1) * limit + 1;
  const end = Math.min(state.page * limit, total);
  if (els.resultRange) {
    els.resultRange.textContent = total === 0
      ? '0件'
      : `${displayNumber.format(start)}–${displayNumber.format(end)} / ${displayNumber.format(total)}`;
  }
  if (els.pageStatus) els.pageStatus.textContent = `${state.page} / ${pages}`;
  if (els.pagePrev) els.pagePrev.disabled = !state.ready || state.page <= 1;
  if (els.pageNext) els.pageNext.disabled = !state.ready || state.page >= pages || total === 0;
  els.pager.hidden = total <= limit;
}

function formatUpdatedAt(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`;
}

async function loadUpdatedAt() {
  if (!els.updatedAt) return;
  const candidates = [
    new URL('./data/meta.json', window.location.href).href,
    new URL('./data/manifest.json', window.location.href).href
  ];
  for (const url of candidates) {
    try {
      const response = await fetch(url, { cache: 'no-cache' });
      if (!response.ok) continue;
      const meta = await response.json();
      const generated = meta.generated_at;
      const label = formatUpdatedAt(generated);
      if (!generated || !label) continue;
      els.updatedAt.dateTime = generated;
      els.updatedAt.textContent = `更新 ${label}`;
      return;
    } catch (error) {
      console.warn('updated_at', url, error);
    }
  }
  if (!els.updatedAt.textContent || els.updatedAt.textContent.includes('—')) {
    els.updatedAt.textContent = '更新 —';
  }
}

const ELECTION_YEARS = {
  shugiin: {
    41: 1996, 42: 2000, 43: 2003,
    44: 2005, 45: 2009, 46: 2012, 47: 2014,
    48: 2017, 49: 2021, 50: 2024, 51: 2026
  },
  sangiin: {
    21: 2007,
    22: 2010,
    23: 2013,
    24: 2016,
    25: 2019,
    26: 2022,
    27: 2025
  }
};

/**
 * 選挙執行日時点の内閣総理大臣（与党首班）。
 * label=表示用漢字、id=管理用ローマ字。
 */
const ELECTION_PM = {
  shugiin: {
    41: { id: 'hashimoto', label: '橋本' },
    42: { id: 'mori', label: '森' },
    43: { id: 'koizumi', label: '小泉' },
    44: { id: 'koizumi', label: '小泉' },
    45: { id: 'aso', label: '麻生' },
    46: { id: 'noda', label: '野田' },
    47: { id: 'abe', label: '安倍' },
    48: { id: 'abe', label: '安倍' },
    49: { id: 'kishida', label: '岸田' },
    50: { id: 'ishiba', label: '石破' },
    51: { id: 'takaichi', label: '高市' }
  },
  sangiin: {
    21: { id: 'abe', label: '安倍' },
    22: { id: 'kan', label: '菅' },
    23: { id: 'abe', label: '安倍' },
    24: { id: 'abe', label: '安倍' },
    25: { id: 'abe', label: '安倍' },
    26: { id: 'kishida', label: '岸田' },
    27: { id: 'ishiba', label: '石破' }
  }
};

const CHAMBER_MARK = { shugiin: '衆', sangiin: '参' };
const DEFAULT_CHAMBER = 'shugiin';

const chamberKey = (chamber = DEFAULT_CHAMBER) => (
  chamber === 'sangiin' || chamber === '参' ? 'sangiin' : 'shugiin'
);

/**
 * 表示用の選挙表記。例: 「2026-衆51回-高市」「2025-参27回-石破」
 * @param {number|string} kaiji
 * @param {'shugiin'|'sangiin'|string} [chamber]
 */
const electionLabel = (kaiji, chamber = DEFAULT_CHAMBER) => {
  const key = chamberKey(chamber);
  const mark = CHAMBER_MARK[key] || '衆';
  const n = Number(kaiji);
  // 年・回次は半角数字に統一（表示の桁ずれ防止）
  const yearRaw = ELECTION_YEARS[key]?.[n];
  const year = yearRaw == null ? null : String(yearRaw).replace(/[０-９]/g, (d) => '０１２３４５６７８９'.indexOf(d));
  const pm = ELECTION_PM[key]?.[n]?.label;
  const body = `${mark}${n}`;
  const withYear = year == null ? body : `${year}-${body}`;
  return pm ? `${withYear}-${pm}` : withYear;
};

const electionYear = (kaiji, chamber = DEFAULT_CHAMBER) => {
  const key = chamberKey(chamber);
  return ELECTION_YEARS[key]?.[Number(kaiji)] ?? '';
};

const electionPmId = (kaiji, chamber = DEFAULT_CHAMBER) => {
  const key = chamberKey(chamber);
  return ELECTION_PM[key]?.[Number(kaiji)]?.id ?? '';
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

const CONTEST_LABELS = {
  smd: '小選挙区',
  district: '県区',
  pr: '比例代表',
  judicial_review: '国民審査',
  all: '全体'
};
const SCOPE_LABELS = { all: '全体', overseas: '在外' };
const GENDER_LABELS = { total: '計', male: '男', female: '女' };
const METRIC_LABELS = {
  candidate_votes: '候補者得票', party_votes: '政党得票',
  pr_list_position: '比例名簿',
  eligible_voters: '有権者数', voters: '投票者数', turnout_rate: '投票率',
  dismissal_yes: '罷免可', dismissal_no: '罷免不可'
};
const GEO_LEVEL_LABELS = {
  prefecture: '都道府県', block: 'ブロック', national: '全国', list: '名簿候補'
};

const TABS = {
  smd: {
    title: '小選挙区',
    note: '選挙区単位の候補者得票（2005-衆44回〜2026-衆51回）。当落・相対得票率・惜敗率は総務省表と選挙区内集計から表示します。衆49回以降は性別列がないため性別は空欄です。',
    keywordLabel: '候補者名',
    keywordPlaceholder: '例：道下大樹',
    metrics: [{ value: 'candidate_votes', label: '候補者得票' }],
    fixedContest: 'smd',
    fixedMetric: 'candidate_votes'
  },
  muni: {
    title: '市町村（詳細）',
    note: '市区町村を選ぶと、小選挙区・比例代表の開票区別得票に加え、同都道府県の有権者・投票・国民審査（都道府県単位）を一覧します。衆院は2009-衆45回〜、参院は第21〜26回など。並びは区分→市町村名降順です。',
    keywordLabel: '候補者・政党名',
    keywordPlaceholder: '例：道下大樹 / 自由民主党',
    metrics: [{ value: 'candidate_votes', label: '横断一覧' }],
    fixedContest: 'smd',
    fixedMetric: 'candidate_votes'
  },
  pr: {
    title: '比例代表',
    note: '政党は全国得票の多い順です。集計単位で全国・ブロック・都道府県を切り替えられます。名簿そのものは「比例名簿」タブです。',
    keywordLabel: '',
    keywordPlaceholder: '',
    metrics: [{ value: 'party_votes', label: '政党得票' }],
    fixedContest: 'pr',
    fixedMetric: 'party_votes'
  },
  prlist: {
    title: '比例名簿',
    note: '衆院は読売紙面の比例ブロック名簿（1996-衆41回〜、当落は比当／小当／落・出典付き）、参院は総務省の比例名簿登載者（全国個人得票・当落）です。',
    keywordLabel: '候補者名',
    keywordPlaceholder: '例：山田太郎',
    metrics: [{ value: 'pr_list_position', label: '比例名簿' }],
    fixedContest: 'pr',
    fixedMetric: 'pr_list_position'
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

const sortPrefectures = (names) => names
  .filter((name) => !['計', '合計', '全国'].includes(name))
  .sort((a, b) => (PREFECTURE_RANK[a] ?? 999) - (PREFECTURE_RANK[b] ?? 999) || a.localeCompare(b, 'ja'));
const districtLabel = (districtNumber) => {
  if (districtNumber == null || districtNumber === '') return '—';
  if (state.chamber === 'sangiin') return `${districtNumber}人区`;
  return `第${districtNumber}区`;
};

/** 参院県区の表示（例: 北海道（3人区）） */
const kenkuLabel = (prefecture, seats) => {
  const pref = prefecture || '—';
  if (seats == null || seats === '') return pref;
  return `${pref}（${seats}人区）`;
};
const contestLabel = (contest) => CONTEST_LABELS[contest] ?? (contest ? String(contest) : '—');
const scopeLabel = (scope) => (scope == null || scope === '' ? '—' : (SCOPE_LABELS[scope] ?? String(scope)));
const genderLabel = (gender) => GENDER_LABELS[gender] ?? (gender ? String(gender) : '—');
const metricLabel = (metric) => METRIC_LABELS[metric] ?? (metric ? String(metric) : '—');
const normalizeBlock = (block) => String(block ?? '').replace(/選挙区$/, '') || '—';
const emptyRow = (cols, message) => `<tr><td colspan="${cols}" class="empty">${message}</td></tr>`;

function prHeaders() {
  const level = els.geoLevel.value;
  if (level === 'national') return ['選挙', '政党', '得票', '相対得票率', '絶対得票率'];
  if (level === 'block') return ['選挙', '比例ブロック', '政党', '得票', '相対得票率', '絶対得票率'];
  if (level === 'list') {
    if (state.chamber === 'shugiin') {
      return ['選挙', '比例ブロック', '政党', '名簿順位', '候補者', '得票', '単位'];
    }
    return els.prefecture.value
      ? ['選挙', '都道府県', '政党', '候補者', '当落', '得票', '単位']
      : ['選挙', '政党', '候補者', '当落', '得票', '単位'];
  }
  if (state.chamber === 'sangiin') {
    const base = ['選挙', '都道府県', '政党', '得票', '相対得票率', '絶対得票率'];
    return showsSourceColumn() ? [...base, '出典'] : base;
  }
  return ['選挙', '比例ブロック', '都道府県', '政党', '得票', '相対得票率', '絶対得票率'];
}

function currentHeaders() {
  if (state.tab === 'smd') {
    if (state.chamber === 'sangiin') {
      return showsSourceColumn()
        ? ['選挙', '県区', '定数', '候補者', '党派', '当落', '得票', '相対得票率', '絶対得票率', '出典']
        : ['選挙', '県区', '定数', '候補者', '党派', '当落', '得票', '相対得票率', '絶対得票率'];
    }
    if (showsSourceColumn()) {
      return ['選挙', '都道府県', '選挙区', '候補者', '党派', '当落', '得票', '相対得票率', '絶対得票率', '惜敗率', '出典'];
    }
    return ['選挙', '都道府県', '選挙区', '候補者', '党派', '当落', '得票', '相対得票率', '惜敗率', '性別'];
  }
  if (state.tab === 'muni') {
    return showsSourceColumn()
      ? ['選挙', '区分', '都道府県', '選挙区', '市区町村', '項目', '党派', '値', '相対得票率', '単位', '粒度', '出典']
      : ['選挙', '区分', '都道府県', '選挙区', '市区町村', '項目', '党派', '値', '相対得票率', '単位', '粒度'];
  }
  if (state.tab === 'pr') {
    const base = prHeaders();
    return showsSourceColumn() && !base.includes('出典') ? [...base, '出典'] : base;
  }
  if (state.tab === 'prlist') {
    if (state.chamber === 'sangiin') {
      return ['選挙', '政党', '候補者', '当落', '得票', '出典'];
    }
    return ['選挙', '比例ブロック', '政党', '名簿順位', '候補者', '重複立候補', '当選枠', '惜敗率', '当落', '出典'];
  }
  if (state.tab === 'turnout') {
    return showsSourceColumn()
      ? ['選挙', '選挙区分', '集計範囲', '地域', '指標', '性別', '値', '単位', '出典']
      : ['選挙', '選挙区分', '集計範囲', '都道府県', '指標', '性別', '値', '単位'];
  }
  return ['選挙', '都道府県', '裁判官', '指標', '値', '単位'];
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
    els.geoLevel, els.prBlock, els.prParty, els.metric, els.keyword, els.electedFilter,
    els.dataSource, els.search, els.resultLimit, els.gender]
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
  let elections;
  if (usesSeijiSource()) {
    if (state.tab === 'muni') elections = state.seijiMuniElections;
    else if (state.tab === 'turnout') elections = state.seijiTurnoutElections;
    else if (state.tab === 'pr') elections = state.seijiPrElections;
    else elections = state.seijiSmdElections;
  } else if (usesUnifiedSource()) {
    const byChamber = state.electionsByChamber?.[state.chamber];
    const mic = byChamber?.[state.tab] ?? state.electionsByTab[state.tab] ?? [];
    let seiji = [];
    if (state.tab === 'muni') seiji = state.seijiMuniElections ?? [];
    else if (state.tab === 'turnout') seiji = state.seijiTurnoutElections ?? [];
    else if (state.tab === 'pr') seiji = state.seijiPrElections ?? [];
    else seiji = state.seijiSmdElections ?? [];
    elections = [...new Set([...mic, ...seiji].map(Number))].sort((a, b) => b - a);
  } else {
    const byChamber = state.electionsByChamber?.[state.chamber];
    elections = byChamber?.[state.tab] ?? state.electionsByTab[state.tab] ?? [];
  }
  fillSelect(els.election, (elections ?? []).map((v) => ({
    value: String(v),
    label: electionLabelForUi(v, state.chamber)
  })));
}

function refreshDistrictOptions() {
  if (state.chamber === 'sangiin' && state.tab === 'smd') {
    const seats = state.seatMagnitudes ?? [];
    fillSelect(els.district, seats.map((d) => ({ value: String(d), label: `${d}人区` })));
    return;
  }
  const pref = els.prefecture.value;
  let source;
  if (usesSeijiSource()) {
    source = state.tab === 'muni' ? state.seijiMuniDistrictsByPref : state.seijiDistrictsByPref;
  } else if (usesUnifiedSource()) {
    const mic = state.tab === 'muni' ? state.muniDistrictsByPref : state.districtsByPref;
    const seiji = state.tab === 'muni' ? state.seijiMuniDistrictsByPref : state.seijiDistrictsByPref;
    source = {};
    for (const key of new Set([...Object.keys(mic || {}), ...Object.keys(seiji || {})])) {
      source[key] = [...new Set([...(mic?.[key] || []), ...(seiji?.[key] || [])])].sort((a, b) => a - b);
    }
  } else {
    source = state.tab === 'muni' ? state.muniDistrictsByPref : state.districtsByPref;
  }
  let districts = [];
  if (pref && source[pref]) districts = source[pref];
  else districts = [...new Set(Object.values(source).flat())].sort((a, b) => a - b);
  fillSelect(els.district, districts.map((d) => ({ value: String(d), label: `第${d}区` })));
}

async function refreshMunicipalityOptions() {
  if (!els.municipality) return;
  const seiji = usesSeijiSource();
  const unified = usesUnifiedSource();
  const canMic = state.hasMunicipality;
  const canSeiji = state.hasSeijiSmdMuni || state.hasSeijiPrMuni;
  if ((!seiji && !unified && !canMic) || ((seiji || unified) && !canSeiji && !canMic) || !state.conn) {
    fillSelect(els.municipality, []);
    return;
  }
  const parts = [`municipality IS NOT NULL`];
  if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
  if (els.prefecture.value) parts.push(`prefecture = '${escapeSql(els.prefecture.value)}'`);
  if (els.district.value) parts.push(`district_number = ${Number(els.district.value)}`);
  try {
    const unions = [];
    if ((!seiji || unified) && canMic) {
      const micParts = [...parts];
      if (state.chamber === 'sangiin') micParts.push(`chamber = 'sangiin'`);
      else micParts.push(`(chamber IS NULL OR chamber = 'shugiin')`);
      unions.push(`SELECT DISTINCT ${municipalityNormSql('municipality')} AS municipality FROM read_parquet('municipality_facts.parquet') WHERE ${micParts.join(' AND ')}`);
    }
    if ((seiji || unified) && state.hasSeijiSmdMuni) {
      unions.push(`SELECT DISTINCT ${municipalityNormSql('municipality')} AS municipality FROM read_parquet('seiji_gakkai_smd_municipality_votes.parquet') WHERE ${parts.join(' AND ')}`);
    }
    if ((seiji || unified) && state.hasSeijiPrMuni) {
      unions.push(`SELECT DISTINCT ${municipalityNormSql('municipality')} AS municipality FROM read_parquet('seiji_gakkai_pr_municipality_votes.parquet') WHERE ${parts.join(' AND ')}`);
    }
    if (!unions.length) {
      fillSelect(els.municipality, []);
      return;
    }
    const result = await state.conn.query(`
      SELECT DISTINCT municipality FROM (${unions.join(' UNION ')})
      ORDER BY municipality`);
    const names = result.toArray().map((row) => normalizeMunicipalityLabel(String(row.toJSON().municipality)));
    fillSelect(els.municipality, sortMunicipalities([...new Set(names)]).map((name) => ({ value: name, label: name })));
  } catch (error) {
    console.error(error);
    fillSelect(els.municipality, []);
  }
}

function refreshPrefectureOptions() {
  let names;
  if (usesSeijiSource()) {
    if (state.tab === 'muni') names = state.seijiMuniPrefectures;
    else if (state.tab === 'turnout' && els.contest?.value === 'pr') {
      names = state.seijiPrBlocks;
    } else if (state.tab === 'turnout') names = state.seijiTurnoutPrefectures;
    else if (state.tab === 'pr') names = [];
    else names = state.seijiPrefectures;
  } else if (usesUnifiedSource()) {
    if (state.tab === 'muni') {
      names = sortPrefectures([...new Set([...(state.muniPrefectures || []), ...(state.seijiMuniPrefectures || [])])]);
    } else if (state.tab === 'turnout' && els.contest?.value === 'pr') {
      names = [...new Set([...(state.seijiPrBlocks || [])])];
    } else if (state.tab === 'turnout') {
      names = sortPrefectures([...new Set([...(state.allPrefectures || []), ...(state.seijiTurnoutPrefectures || [])])]);
    } else if (state.tab === 'pr') {
      names = state.allPrefectures;
    } else {
      names = sortPrefectures([...new Set([...(state.allPrefectures || []), ...(state.seijiPrefectures || [])])]);
    }
  } else {
    names = state.tab === 'muni' ? state.muniPrefectures : state.allPrefectures;
  }
  fillSelect(els.prefecture, (names ?? []).map((v) => ({ value: v, label: v })));
}

function municipalitySortKey(name) {
  const n = String(name || '');
  let type = 5;
  if (n.endsWith('市') && !n.includes('（')) type = 0;
  else if (n.endsWith('区')) type = 1;
  else if (n.endsWith('町')) type = 2;
  else if (n.endsWith('村')) type = 3;
  if (n.includes('振興局') || n.endsWith('計') || n.includes('合計') || /（\d+区）/.test(n)) type = 9;
  return type;
}

function sortMunicipalities(names) {
  return [...names].sort((a, b) => {
    const ta = municipalitySortKey(a);
    const tb = municipalitySortKey(b);
    return ta - tb || String(a).localeCompare(String(b), 'ja');
  });
}

function refreshPartyOptions() {
  if (!els.prParty) return;
  const kaiji = els.election.value ? Number(els.election.value) : null;
  const useYomi = state.tab === 'prlist' && state.chamber === 'shugiin' && state.hasYomiPrMeibo;
  const useSmd = state.tab === 'smd';
  const useSeiji = usesSeijiSource() && (state.tab === 'pr' || state.tab === 'smd');
  const useUnified = usesUnifiedSource() && (state.tab === 'pr' || state.tab === 'smd');
  const micStore = useSmd ? (state.partiesByElectionSmd || {}) : (state.partiesByElection || {});
  const seijiStore = useSmd ? (state.partiesByElectionSeijiSmd || {}) : (state.partiesByElectionSeiji || {});
  const store = useYomi
    ? (state.partiesByElectionYomi || {})
    : (useSeiji ? seijiStore : micStore);
  let rawParties = [];
  const pushFrom = (src, key) => {
    const list = src[key] ?? [];
    for (const name of list) {
      if (!rawParties.includes(name)) rawParties.push(name);
    }
  };
  if (kaiji != null) {
    const eid = `${chamberPrefix()}${kaiji}`;
    if (useUnified) {
      pushFrom(micStore, eid);
      pushFrom(micStore, kaiji);
      pushFrom(seijiStore, eid);
      pushFrom(seijiStore, kaiji);
    } else {
      rawParties = store[eid]
        ?? (state.chamber === 'shugiin' && !useYomi ? store[kaiji] : null)
        ?? [];
    }
  } else {
    const elections = useSmd
      ? (useSeiji
        ? (state.seijiSmdElections ?? [])
        : useUnified
          ? [...new Set([
            ...(state.electionsByChamber?.[state.chamber]?.smd ?? state.electionsByTab.smd ?? []),
            ...(state.seijiSmdElections ?? [])
          ])].sort((a, b) => b - a)
          : (state.electionsByChamber?.[state.chamber]?.smd ?? state.electionsByTab.smd ?? []))
      : (useSeiji
        ? (state.seijiPrElections ?? [])
        : useUnified
          ? [...new Set([
            ...(state.electionsByChamber?.[state.chamber]?.pr ?? state.electionsByTab.pr ?? []),
            ...(state.seijiPrElections ?? [])
          ])].sort((a, b) => b - a)
          : (state.electionsByChamber?.[state.chamber]?.[useYomi ? 'prlist' : 'pr']
            ?? state.electionsByTab[useYomi ? 'prlist' : 'pr']
            ?? []));
    const seenRaw = new Set();
    for (const k of elections) {
      const keys = [`${chamberPrefix()}${k}`];
      if (state.chamber === 'shugiin' && !useYomi) keys.push(k);
      for (const key of keys) {
        const lists = useUnified
          ? [micStore[key] || [], seijiStore[key] || []]
          : [store[key] || []];
        for (const list of lists) {
          for (const name of list) {
            if (!seenRaw.has(name)) {
              seenRaw.add(name);
              rawParties.push(name);
            }
          }
        }
      }
    }
  }

  // プルダウンは正本名にそろえる（略称はフィルタ展開で拾う）。外側括弧は外す
  const seenCanon = new Set();
  const parties = [];
  for (const name of rawParties) {
    const canon = stripOuterPartyParens(useYomi ? name : canonicalPartyName(name, kaiji));
    if (!canon || seenCanon.has(canon)) continue;
    seenCanon.add(canon);
    parties.push(canon);
  }
  fillSelect(els.prParty, parties.map((name) => ({ value: name, label: name })));
}

function chamberPrefix() {
  return state.chamber === 'sangiin' ? 'sangiin-' : 'shugiin-';
}

function chamberSql() {
  return `election_id LIKE '${chamberPrefix()}%'`;
}

function syncContestOptions() {
  if (!els.contest) return;
  const current = els.contest.value;
  if (state.chamber === 'sangiin') {
    els.contest.innerHTML = [
      '<option value="">すべて</option>',
      '<option value="district">県区</option>',
      '<option value="pr">比例代表</option>'
    ].join('');
  } else {
    els.contest.innerHTML = [
      '<option value="">すべて</option>',
      '<option value="smd">小選挙区</option>',
      '<option value="pr">比例代表</option>',
      '<option value="judicial_review">国民審査</option>'
    ].join('');
  }
  const values = [...els.contest.options].map((o) => o.value);
  els.contest.value = values.includes(current) ? current : '';
}

function applyChamber(chamberId) {
  state.chamber = chamberId === 'sangiin' ? 'sangiin' : 'shugiin';
  if (els.form) els.form.dataset.chamber = state.chamber;
  $$('.chamber').forEach((button) => {
    const active = button.dataset.chamber === state.chamber;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if (els.chamberShugiin) els.chamberShugiin.hidden = false;
  if (els.chamberSangiin) els.chamberSangiin.hidden = state.chamber !== 'sangiin';

  const cov = state.electionsByChamber?.[state.chamber];
  if (cov) {
    state.electionsByTab = {
      smd: cov.smd ?? [],
      pr: cov.pr ?? [],
      prlist: cov.prlist ?? cov.pr ?? [],
      turnout: cov.turnout ?? [],
      judicial: cov.judicial ?? [],
      muni: cov.muni ?? []
    };
    state.allPrefectures = cov.prefectures ?? state.allPrefectures;
  }
  if (state.muniPrefecturesByChamber?.[state.chamber]) {
    state.muniPrefectures = state.muniPrefecturesByChamber[state.chamber];
  }
  if (state.muniDistrictsByChamber?.[state.chamber]) {
    state.muniDistrictsByPref = state.muniDistrictsByChamber[state.chamber];
  }

  $$('.tab').forEach((button) => {
    const tab = button.dataset.tab;
    const sangiinOk = tab === 'turnout' || tab === 'pr' || tab === 'smd' || tab === 'prlist'
      || (tab === 'muni' && state.hasMunicipality && (state.electionsByChamber?.sangiin?.muni?.length > 0));
    const allowed = state.chamber === 'shugiin' || sangiinOk;
    button.hidden = !allowed;
    button.disabled = !allowed;
    if (tab === 'smd') {
      button.textContent = state.chamber === 'sangiin' ? '県区' : '小選挙区';
    }
    if (tab === 'muni') {
      button.textContent = '市町村（詳細）';
    }
  });

  // 参院の比例はブロックなし → ブロック選択肢を隠す。衆院比例の名簿候補は prlist タブへ。
  const blockOpt = els.geoLevel && [...els.geoLevel.options].find((o) => o.value === 'block');
  const listOpt = els.geoLevel && [...els.geoLevel.options].find((o) => o.value === 'list');
  if (blockOpt) blockOpt.hidden = state.chamber === 'sangiin';
  if (listOpt) listOpt.hidden = state.chamber !== 'sangiin';
  if (state.chamber === 'sangiin' && els.geoLevel?.value === 'block') {
    els.geoLevel.value = 'national';
  }
  if (state.chamber === 'shugiin' && els.geoLevel?.value === 'list') {
    els.geoLevel.value = 'prefecture';
  }

  // 比例名簿のブロックフィルタは衆院のみ
  if (els.prBlock) {
    const blockWrap = els.prBlock.closest('label');
    if (blockWrap && state.tab === 'prlist') {
      blockWrap.hidden = state.chamber === 'sangiin';
    }
  }

  // 参院県区: 定数（1人区等）で絞り込み。衆院は第N区。市区町村タブの参院は定数なし。
  if (els.district) {
    const districtWrap = els.district.closest('label');
    if (districtWrap) {
      const hideDistrict = state.chamber === 'sangiin' && state.tab === 'muni';
      districtWrap.hidden = hideDistrict;
      const labelText = districtWrap.childNodes[0];
      if (labelText && labelText.nodeType === Node.TEXT_NODE) {
        labelText.textContent = state.chamber === 'sangiin' ? '定数' : '選挙区';
      }
    }
  }

  syncContestOptions();

  const fallbackTab = state.chamber === 'sangiin'
    ? (['turnout', 'pr', 'prlist', 'smd', 'muni'].includes(state.tab) ? state.tab : 'smd')
    : (TABS[state.tab] ? state.tab : 'smd');
  if (state.ready) {
    refreshElectionOptions();
    applyTab(fallbackTab, { search: false });
  }
}

function commonFiltersMuni(includePref, includeDistrict, alias = '') {
  const p = alias ? `${alias}.` : '';
  const parts = [];
  if (els.election.value) parts.push(`${p}election_kaiji = ${Number(els.election.value)}`);
  if (includePref && els.prefecture.value) parts.push(`${p}prefecture = '${escapeSql(els.prefecture.value)}'`);
  if (includeDistrict && els.district.value) parts.push(`${p}district_number = ${Number(els.district.value)}`);
  if (els.municipality.value) {
    parts.push(municipalityFilterSql(`${p}municipality`));
  }
  return parts;
}

function whereClauseSeijiMuni(alias = '') {
  const parts = commonFiltersMuni(true, true, alias);
  if (els.keyword.value.trim()) {
    const p = alias ? `${alias}.` : '';
    const partsKeyword = [
      keywordCompactSql(`${p}subject`),
      keywordCompactSql(`${p}party`),
      keywordPersonAliasSql(`${p}subject`, `${p}subject`)
    ].filter(Boolean);
    parts.push(`(${partsKeyword.join(' OR ')})`);
  }
  return parts.join(' AND ') || '1=1';
}

function clearResultsIdle(message = '条件を選んで「検索する」を押してください') {
  state.rows = [];
  state.matchTotal = 0;
  state.page = 1;
  updatePager();
  if (els.resultLabel) els.resultLabel.textContent = '検索条件を選択してください';
  if (els.download) els.download.disabled = true;
  els.results.innerHTML = emptyRow(currentHeaders().length, message);
}

function applyTab(tabId, { search = false } = {}) {
  if (state.chamber === 'sangiin' && !['turnout', 'pr', 'prlist', 'smd', 'muni'].includes(tabId)) {
    tabId = 'smd';
  }
  state.tab = tabId;
  const tab = TABS[tabId];
  els.form.dataset.tab = tabId;
  syncDataSourceUi();
  els.keyword.value = '';
  els.district.value = '';
  els.municipality.value = '';
  els.prBlock.value = '';
  if (els.prParty) els.prParty.value = '';
  refreshElectedFilterOptions();
  if (els.electedFilter) els.electedFilter.value = '';
  els.prefecture.value = '';
  if (tabId === 'pr') {
    if (state.chamber === 'sangiin') els.geoLevel.value = 'national';
    else if (usesSeijiSource() || usesUnifiedSource()) els.geoLevel.value = 'block';
    else els.geoLevel.value = 'prefecture';
  }
  if (tabId === 'turnout') els.scope.value = 'all';
  els.form.dataset.geolevel = els.geoLevel.value || 'prefecture';
  $$('.tab').forEach((button) => {
    const active = button.dataset.tab === tabId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if (tabId === 'pr' && state.chamber === 'sangiin') {
    els.tabNote.textContent = '参院の比例です。全国／都道府県は政党得票、名簿候補は個人名得票です。名簿一覧は「比例名簿」タブです。';
  } else if (tabId === 'prlist' && state.chamber === 'sangiin') {
    els.tabNote.textContent = '参院の比例名簿登載者（全国の個人得票・当落）です。都道府県別の個人得票は比例代表タブの「名簿候補」で都道府県を指定してください。出典は source_code です。';
  } else if (tabId === 'prlist' && state.chamber === 'shugiin') {
    els.tabNote.textContent = '読売新聞紙面の比例ブロック名簿です（1996-衆41回〜）。当落は紙面の比当／小当／落で絞り込めます。出典列で紙面由来を確認できます。惜敗率は紙面に無い行が多く空欄になります。';
  } else if (tabId === 'turnout' && state.chamber === 'sangiin') {
    els.tabNote.textContent = '参院の都道府県単位の有権者数・投票者数・投票率です。選挙区／比例を切り替えられます。';
  } else if (tabId === 'smd' && state.chamber === 'sangiin') {
    els.tabNote.textContent = '参院の県区（都道府県・合区）候補者得票です。候補者名は得票一致の範囲で読売CD表記を優先し、出典列で MIC／関西大／読売CD を区別します。';
  } else if (tabId === 'muni' && state.chamber === 'sangiin') {
    els.tabNote.textContent = '参院第25・26回などの市区町村別得票です。選挙区候補者・比例政党・比例名簿候補者を横断検索できます。';
  } else if (usesSeijiSource() && tabId === 'smd') {
    els.tabNote.textContent = '政治学会SH-Dの小選挙区得票（1996-衆〜2017-衆・二次ソース）です。候補者名はかな表記です。総務省正本とは別系統で、当落・惜敗率はありません。';
  } else if (usesSeijiSource() && tabId === 'muni') {
    els.tabNote.textContent = '政治学会SH-Dの市区町村別得票（1996-衆〜2017-衆・二次ソース）です。候補者名はかな表記です。総務省正本とは混ぜていません。';
  } else if (usesSeijiSource() && tabId === 'turnout') {
    els.tabNote.textContent = '政治学会の投票・有権者（小選挙区=都道府県合算、比例=ブロック／全国）です。在外区分はありません。';
  } else if (usesSeijiSource() && tabId === 'pr') {
    els.tabNote.textContent = '政治学会SH-Bの比例政党得票（1996-衆〜2017-衆）です。集計単位はブロック／全国のみ（都道府県粒なし）。';
  } else {
    els.tabNote.textContent = tab.note;
  }

  if (els.district) {
    const districtWrap = els.district.closest('label');
    if (districtWrap) {
      districtWrap.hidden = state.chamber === 'sangiin' && tabId === 'muni';
    }
  }
  if (els.prBlock) {
    const blockWrap = els.prBlock.closest('label');
    if (blockWrap) {
      // CSS data-show と併用。参院比例名簿ではブロック非表示。
      if (tabId === 'prlist' && state.chamber === 'sangiin') blockWrap.hidden = true;
      else blockWrap.hidden = false;
    }
  }

  els.metric.innerHTML = tab.metrics.map((m) => `<option value="${m.value}">${m.label}</option>`).join('');
  if (tab.fixedMetric) els.metric.value = tab.fixedMetric;
  if (tab.fixedContest) els.contest.value = tab.fixedContest;
  else els.contest.value = '';

  if (tabId === 'pr' && state.chamber === 'sangiin' && els.geoLevel.value === 'list') {
    els.keywordLabel.textContent = '候補者名';
    els.keyword.placeholder = '例：山田太郎';
  } else if (tab.keywordLabel) {
    els.keywordLabel.textContent = tab.keywordLabel;
    els.keyword.placeholder = tab.keywordPlaceholder;
  }

  syncDataSourceUi();
  refreshElectionOptions();
  refreshPrefectureOptions();
  refreshDistrictOptions();
  refreshPartyOptions();
  if (usesSeijiSource() && (state.tab === 'smd' || state.tab === 'muni')) {
    els.keywordLabel.textContent = '候補者名（かな可）';
    els.keyword.placeholder = '例：ヨコミチタカヒロ';
  }
  els.head.innerHTML = currentHeaders().map((h) => (
    h === '得票' || h === '値' || h === '相対得票率' || h === '絶対得票率' || h === '惜敗率'
      || h === '名簿順位' || h === '当選枠'
      ? `<th class="numeric">${h}</th>`
      : `<th>${h}</th>`
  )).join('');

  const finish = async () => {
    if (!(search && state.ready)) clearResultsIdle();
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
    parts.push(municipalityFilterSql('municipality'));
  }
  return parts;
}


function whereClauseSeijiSmd(alias = '') {
  const p = alias ? `${alias}.` : '';
  const parts = [
    `${p}metric = 'candidate_votes'`,
    `${p}contest = 'smd'`,
    ...commonFilters({ includePref: true, includeDistrict: true }).map((x) => {
      if (!alias) return x;
      return x
        .replace(/^election_kaiji/, `${p}election_kaiji`)
        .replace(/^prefecture /, `${p}prefecture `)
        .replace(/^district_number/, `${p}district_number`);
    })
  ];
  const outcome = els.electedFilter?.value;
  if (usesSeijiSource()) {
    if (outcome === 'smd' || outcome === 'pr' || outcome === 'loss') {
      parts.push(`${p}outcome = '${outcome}'`);
    }
  } else if (usesUnifiedSource()) {
    if (outcome === 'won') parts.push(`(${p}elected_smd = true OR ${p}outcome = 'smd')`);
    else if (outcome === 'lost') parts.push(`(${p}elected_smd = false OR ${p}outcome = 'loss')`);
  }
  if (els.keyword.value.trim()) {
    const cand = state.hasSeijiNameMap && alias
      ? `coalesce(nm.kanji, ${p}candidate)`
      : `${p}candidate`;
    const partsKeyword = [
      keywordCompactSql(cand),
      keywordCompactSql(`${p}candidate_raw`),
      keywordCompactSql(`${p}party`),
      keywordPersonAliasSql(cand, `${p}candidate_raw`)
    ].filter(Boolean);
    parts.push(`(${partsKeyword.join(' OR ')})`);
  }
  return parts.join(' AND ');
}



function whereClauseSmdBase() {
  const contest = state.chamber === 'sangiin' ? 'district' : 'smd';
  return [
    chamberSql(),
    `metric = 'candidate_votes'`,
    `contest = '${contest}'`,
    ...commonFilters({ includePref: true, includeDistrict: true })
  ].join(' AND ');
}

/** 相対得票率の外側で適用（当選のみ等で分母が壊れないようにする） */
function smdResultFilterSql(alias = '') {
  const p = alias ? `${alias}.` : '';
  const parts = [];
  if (els.electedFilter?.value === 'won') parts.push(`${p}elected = true`);
  else if (els.electedFilter?.value === 'lost') parts.push(`${p}elected = false`);
  if (els.keyword.value.trim()) {
    const cand = `${p}candidate`;
    const raw = `${p}candidate_raw`;
    const partsKeyword = [
      keywordCompactSql(cand),
      keywordCompactSql(raw),
      keywordCompactSql(`${p}party`),
      keywordPersonAliasSql(cand, raw)
    ].filter(Boolean);
    if (partsKeyword.length) parts.push(`(${partsKeyword.join(' OR ')})`);
  }
  if (!parts.length) return '';
  return `AND ${parts.join(' AND ')}`;
}

function whereClauseSmd() {
  // 互換: 旧呼び出し向け。相対得票率を含む検索では whereClauseSmdBase + smdResultFilterSql を使う
  const parts = [whereClauseSmdBase()];
  const extra = smdResultFilterSql().replace(/^AND\s+/, '');
  if (extra) parts.push(extra);
  return parts.join(' AND ');
}

function whereClauseMuniCore() {
  const parts = [...commonFilters({ includePref: true, includeDistrict: false, includeMunicipality: true })];
  if (state.chamber === 'sangiin') {
    parts.unshift(`chamber = 'sangiin'`);
  } else {
    // 衆院: chamber 列が無い旧parquet / shugiin の両方に対応
    parts.unshift(`(chamber IS NULL OR chamber = 'shugiin')`);
  }
  // district filter applies only to SMD rows inside the UNION
  if (els.keyword.value.trim()) {
    const partsKeyword = [
      keywordCompactSql('subject'),
      keywordCompactSql('party'),
      keywordCompactSql('candidate'),
      keywordPersonAliasSql('subject', 'subject'),
      keywordPersonAliasSql('candidate', 'candidate')
    ].filter(Boolean);
    parts.push(`(${partsKeyword.join(' OR ')})`);
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
      WHERE ${municipalityFilterSql('municipality')} AND prefecture IS NOT NULL
    )`);
  }
  return parts.join(' AND ');
}

function whereClauseTurnout() {
  const parts = [chamberSql(), `metric = '${escapeSql(els.metric.value)}'`];
  if (els.contest.value) parts.push(`contest = '${escapeSql(els.contest.value)}'`);
  if (els.scope.value === 'all') parts.push(`(scope = 'all' OR scope IS NULL)`);
  else if (els.scope.value) parts.push(`scope = '${escapeSql(els.scope.value)}'`);
  if (els.gender && els.gender.value) parts.push(`gender = '${escapeSql(els.gender.value)}'`);
  parts.push(...commonFilters({ includePref: true }));
  return parts.join(' AND ');
}

function whereClauseJudicial() {
  const parts = [
    chamberSql(),
    `metric = '${escapeSql(els.metric.value)}'`,
    `contest = 'judicial_review'`,
    ...commonFilters({ includePref: true })
  ];
  if (els.keyword.value.trim()) {
    parts.push(keywordCompactSql('justice'));
  }
  return parts.join(' AND ');
}

function selectSql() {
  if (state.tab === 'smd') {
    const partyFilter = partyFilterSql('party', 'election_kaiji');
    const resultFilter = smdResultFilterSql();
    if (usesSeijiSource() || usesUnifiedSource()) {
      const candExpr = seijiDisplayCandidateSql('s');
      const seijiSelect = `
        SELECT s.election_kaiji, s.prefecture, s.prefecture_code, s.district_number,
          ${candExpr} AS candidate,
          s.candidate_raw, s.party, s.dual_candidacy, s.value, s.unit, s.source_code,
          s.outcome, s.outcome_label, s.elected_smd, s.is_pr_winner, s.vote_rank, s.sekihairitsu,
          ${personCanonicalJoinSql(candExpr)},
          CASE
            WHEN coalesce(s.district_valid_votes, 0) > 0 THEN 100.0 * s.value / s.district_valid_votes
            WHEN sum(s.value) OVER (
              PARTITION BY s.election_kaiji, s.prefecture, s.district_number
            ) > 0
            THEN 100.0 * s.value / sum(s.value) OVER (
              PARTITION BY s.election_kaiji, s.prefecture, s.district_number
            )
            ELSE NULL
          END AS relative_share,
          CASE
            WHEN coalesce(s.district_eligible_voters, 0) > 0
              THEN 100.0 * s.value / s.district_eligible_voters
            WHEN s.absolute_vote_rate IS NULL THEN NULL
            /* CAN 42–45 は割合(0–1)、他回は％。有権者が無いときだけ補正 */
            WHEN s.absolute_vote_rate <= 1 THEN 100.0 * s.absolute_vote_rate
            ELSE s.absolute_vote_rate
          END AS absolute_share,
          s.sekihairitsu AS sekihai_rate,
          CAST(NULL AS VARCHAR) AS gender,
          coalesce(s.elected_smd, false) AS elected
        FROM read_parquet('seiji_gakkai_smd_district_votes.parquet') s
        ${seijiNameMapJoinSql('s')}
        WHERE ${whereClauseSeijiSmd('s')}`;

      if (usesSeijiSource()) {
        return `
          SELECT * FROM (${seijiSelect}) scored
          WHERE 1=1 ${resultFilter} ${partyFilter}
          ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, district_number NULLS LAST, value DESC NULLS LAST
          ${limitOffsetSql()}`;
      }

      // 統合: MIC 優先。同一(回・県・区)に MIC があれば政治学会は出さない
      return `
        WITH mic AS (
          SELECT election_kaiji, prefecture, prefecture_code, district_number,
            candidate, candidate_raw, party,
            CAST(NULL AS BOOLEAN) AS dual_candidacy,
            value, unit, source_code,
            CAST(NULL AS VARCHAR) AS outcome,
            CAST(NULL AS VARCHAR) AS outcome_label,
            elected AS elected_smd,
            CAST(NULL AS BOOLEAN) AS is_pr_winner,
            CAST(NULL AS BIGINT) AS vote_rank,
            sekihairitsu,
            ${personCanonicalJoinSql('candidate')},
            CASE
              WHEN sum(value) OVER (
                PARTITION BY election_kaiji, prefecture, district_number
              ) > 0
              THEN 100.0 * value / sum(value) OVER (
                PARTITION BY election_kaiji, prefecture, district_number
              )
              ELSE NULL
            END AS relative_share,
            CAST(NULL AS DOUBLE) AS absolute_share,
            coalesce(
              sekihairitsu,
              CASE
                WHEN max(CASE WHEN elected THEN value END) OVER (
                  PARTITION BY election_kaiji, prefecture, district_number
                ) > 0
                THEN 100.0 * value / max(CASE WHEN elected THEN value END) OVER (
                  PARTITION BY election_kaiji, prefecture, district_number
                )
                ELSE NULL
              END
            ) AS sekihai_rate,
            gender,
            elected
          FROM read_parquet('facts.parquet') WHERE ${whereClauseSmdBase()}
        ),
        seiji AS (
          ${seijiSelect}
            AND NOT EXISTS (
              SELECT 1 FROM mic m
              WHERE m.election_kaiji = s.election_kaiji
                AND m.prefecture = s.prefecture
                AND m.district_number = s.district_number
            )
        ),
        combined AS (
          SELECT election_kaiji, prefecture, prefecture_code, district_number,
                 candidate, candidate_raw, party, dual_candidacy, value, unit, source_code,
                 outcome, outcome_label, elected_smd, is_pr_winner, vote_rank, sekihairitsu,
                 canonical_name, relative_share, absolute_share, sekihai_rate, gender, elected
          FROM mic
          UNION ALL BY NAME
          SELECT election_kaiji, prefecture, prefecture_code, district_number,
                 candidate, candidate_raw, party, dual_candidacy, value, unit, source_code,
                 outcome, outcome_label, elected_smd, is_pr_winner, vote_rank, sekihairitsu,
                 canonical_name, relative_share, absolute_share, sekihai_rate, gender, elected
          FROM seiji
        )
        SELECT * FROM combined
        WHERE 1=1 ${resultFilter} ${partyFilter}
        ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, district_number NULLS LAST, value DESC NULLS LAST
        ${limitOffsetSql()}`;
    }
    if (state.chamber === 'sangiin') {
      const yomiName = state.hasSangiinYomiNameMap ? 'ym.yomi_name' : 'NULL::VARCHAR';
      return `
        WITH base AS (
          SELECT * FROM read_parquet('facts.parquet')
          WHERE ${whereClauseSmdBase()}
        ),
        cand AS (
          SELECT b.election_kaiji, b.prefecture, b.prefecture_code, b.district_number,
            b.candidate, b.candidate_raw, b.party, b.value, b.unit, b.source_code, b.elected, b.row_variant,
            ${yomiName} AS yomi_name,
            ${personCanonicalJoinSql('b.candidate')}
          FROM base b
          ${sangiinYomiPrefJoinSql('b')}
        ),
        eligible AS (
          SELECT election_kaiji, prefecture, max(value) AS eligible_voters
          FROM read_parquet('facts.parquet')
          WHERE election_id LIKE 'sangiin-%'
            AND contest = 'district' AND metric = 'eligible_voters'
            AND gender = 'total' AND (scope = 'all' OR scope IS NULL)
            AND prefecture IS NOT NULL
          GROUP BY election_kaiji, prefecture
        ),
        scored AS (
          SELECT c.*,
            CASE WHEN sum(c.value) OVER (PARTITION BY c.election_kaiji, c.prefecture) > 0
              THEN 100.0 * c.value / sum(c.value) OVER (PARTITION BY c.election_kaiji, c.prefecture)
              ELSE NULL END AS relative_share,
            CASE WHEN e.eligible_voters > 0
              THEN 100.0 * c.value / e.eligible_voters
              ELSE NULL END AS absolute_share
          FROM cand c
          LEFT JOIN eligible e
            ON c.election_kaiji = e.election_kaiji AND c.prefecture = e.prefecture
        )
        SELECT * FROM scored
        WHERE 1=1 ${resultFilter} ${partyFilter}
        ORDER BY election_kaiji DESC, district_number NULLS LAST, prefecture_code NULLS LAST, value DESC NULLS LAST
        ${limitOffsetSql()}`;
    }
    return `
      WITH scored AS (
        SELECT election_kaiji, prefecture, prefecture_code, district_number,
          candidate, candidate_raw, party, gender, elected, value, unit, source_code,
          ${personCanonicalJoinSql('candidate')},
          CASE
            WHEN sum(value) OVER (
              PARTITION BY election_kaiji, prefecture, district_number
            ) > 0
            THEN 100.0 * value / sum(value) OVER (
              PARTITION BY election_kaiji, prefecture, district_number
            )
            ELSE NULL
          END AS relative_share,
          coalesce(
            sekihairitsu,
            CASE
              WHEN max(CASE WHEN elected THEN value END) OVER (
                PARTITION BY election_kaiji, prefecture, district_number
              ) > 0
              THEN 100.0 * value / max(CASE WHEN elected THEN value END) OVER (
                PARTITION BY election_kaiji, prefecture, district_number
              )
              ELSE NULL
            END
          ) AS sekihai_rate
          FROM read_parquet('facts.parquet') WHERE ${whereClauseSmdBase()}
      )
      SELECT * FROM scored
      WHERE 1=1 ${resultFilter} ${partyFilter}
      ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, district_number NULLS LAST, value DESC NULLS LAST
      ${limitOffsetSql()}`;
  }

  if (state.tab === 'muni') {
    if (usesSeijiSource() || usesUnifiedSource()) {
      const seijiSmd = state.hasSeijiSmdMuni ? `
        SELECT s.election_kaiji, s.category, s.prefecture, s.prefecture_code, s.district_number,
               ${municipalityNormSql('s.municipality')} AS municipality,
               CASE s.metric
                 WHEN 'eligible_voters' THEN '有権者数'
                 WHEN 'voters' THEN '投票者数'
                 ELSE coalesce(nm.kanji, s.candidate)
               END AS subject,
               s.party, s.value, s.unit, s.grain, s.source_code, s.metric,
               CASE
                 WHEN s.metric = 'candidate_votes'
                   AND sum(s.value) OVER (
                     PARTITION BY s.election_kaiji, s.prefecture, ${municipalityNormSql('s.municipality')}, s.metric
                   ) > 0
                 THEN 100.0 * s.value / sum(s.value) OVER (
                   PARTITION BY s.election_kaiji, s.prefecture, ${municipalityNormSql('s.municipality')}, s.metric
                 )
                 ELSE NULL
               END AS relative_share,
               0 AS category_rank
        FROM read_parquet('seiji_gakkai_smd_municipality_votes.parquet') s
        ${seijiMuniNameMapJoinSql('s')}
        WHERE ${whereClauseSeijiMuni('s')}` : null;
      const seijiPr = state.hasSeijiPrMuni ? `
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               ${municipalityNormSql('municipality')} AS municipality,
               CASE metric
                 WHEN 'eligible_voters' THEN '有権者数'
                 WHEN 'voters' THEN '投票者数'
                 ELSE subject
               END AS subject,
               party, value, unit, grain, source_code, metric,
               CASE
                 WHEN metric = 'party_votes'
                   AND sum(value) OVER (
                     PARTITION BY election_kaiji, prefecture, ${municipalityNormSql('municipality')}, metric
                   ) > 0
                 THEN 100.0 * value / sum(value) OVER (
                   PARTITION BY election_kaiji, prefecture, ${municipalityNormSql('municipality')}, metric
                 )
                 ELSE NULL
               END AS relative_share,
               1 AS category_rank
        FROM read_parquet('seiji_gakkai_pr_municipality_votes.parquet')
        WHERE ${whereClauseSeijiMuni()}` : null;

      if (usesSeijiSource()) {
        const parts = [seijiSmd, seijiPr].filter(Boolean);
        return `
          SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
                 municipality, subject, party, value, unit, grain, source_code, relative_share
          FROM (
            ${parts.join('\nUNION ALL BY NAME\n')}
          )
          ORDER BY category_rank, election_kaiji DESC, prefecture_code NULLS LAST,
                   district_number NULLS LAST, municipality NULLS LAST, value DESC NULLS LAST
          ${limitOffsetSql()}`;
      }

      // 統合: MIC 市町村 + 欠落回の政治学会 SMD/PR muni
      const core = whereClauseMuniCore();
      const smdExtra = whereClauseMuniSmdExtra();
      const prefWhere = whereClausePrefRelated();
      const keyword = els.keyword.value.trim();
      const keywordSql = keyword
        ? `AND (coalesce(CAST(metric AS VARCHAR), '') ILIKE '%${escapeSql(keyword)}%' OR coalesce(justice, '') ILIKE '%${escapeSql(keyword)}%')`
        : '';
      const districtCat = '小選挙区';
      const turnoutContest = 'smd';
      const gapSmd = seijiSmd ? `
        SELECT * FROM (${seijiSmd}) s
        WHERE NOT EXISTS (
          SELECT 1 FROM read_parquet('municipality_facts.parquet') m
          WHERE (m.chamber IS NULL OR m.chamber = 'shugiin')
            AND m.category = '小選挙区'
            AND m.election_kaiji = s.election_kaiji
            AND m.prefecture = s.prefecture
            AND ${municipalityNormSql('m.municipality')} = ${municipalityNormSql('s.municipality')}
        )` : null;
      const gapPr = seijiPr ? `
        SELECT * FROM (${seijiPr}) s
        WHERE NOT EXISTS (
          SELECT 1 FROM read_parquet('municipality_facts.parquet') m
          WHERE (m.chamber IS NULL OR m.chamber = 'shugiin')
            AND m.category = '比例代表'
            AND m.election_kaiji = s.election_kaiji
            AND m.prefecture = s.prefecture
            AND ${municipalityNormSql('m.municipality')} = ${municipalityNormSql('s.municipality')}
        )` : null;
      return `
      WITH muni_rows AS (
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               ${municipalityNormSql('municipality')} AS municipality, subject, party, value, unit, grain, source_code,
               CASE
                 WHEN category IN ('小選挙区', '選挙区', '比例代表')
                   AND sum(value) OVER (
                     PARTITION BY election_kaiji, category, prefecture, ${municipalityNormSql('municipality')}, metric
                   ) > 0
                 THEN 100.0 * value / sum(value) OVER (
                   PARTITION BY election_kaiji, category, prefecture, ${municipalityNormSql('municipality')}, metric
                 )
                 ELSE NULL
               END AS relative_share,
               CASE category
                 WHEN '小選挙区' THEN 0
                 WHEN '選挙区' THEN 0
                 WHEN '比例代表' THEN 1
                 ELSE 9
               END AS category_rank
        FROM read_parquet('municipality_facts.parquet')
        WHERE ${core || '1=1'}
          AND (category = '比例代表' OR (category = '${districtCat}'${smdExtra}))
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
               NULL::DOUBLE AS relative_share,
               2 AS category_rank
        FROM read_parquet('facts.parquet')
        WHERE contest = '${turnoutContest}'
          AND metric IN ('eligible_voters', 'voters', 'turnout_rate')
          AND (scope = 'all' OR scope IS NULL)
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          AND ${chamberSql()}
          ${prefWhere ? `AND ${prefWhere}` : ''}
          ${keywordSql}
          ${els.municipality.value || els.prefecture.value ? '' : 'AND 1=0'}
      ),
      gap_rows AS (
        ${[gapSmd, gapPr].filter(Boolean).length
          ? [gapSmd, gapPr].filter(Boolean).join('\nUNION ALL BY NAME\n')
          : `SELECT
               CAST(NULL AS BIGINT) AS election_kaiji,
               CAST(NULL AS VARCHAR) AS category,
               CAST(NULL AS VARCHAR) AS prefecture,
               CAST(NULL AS VARCHAR) AS prefecture_code,
               CAST(NULL AS INTEGER) AS district_number,
               CAST(NULL AS VARCHAR) AS municipality,
               CAST(NULL AS VARCHAR) AS subject,
               CAST(NULL AS VARCHAR) AS party,
               CAST(NULL AS BIGINT) AS value,
               CAST(NULL AS VARCHAR) AS unit,
               CAST(NULL AS VARCHAR) AS grain,
               CAST(NULL AS VARCHAR) AS source_code,
               CAST(NULL AS DOUBLE) AS relative_share,
               CAST(NULL AS INTEGER) AS category_rank
             WHERE 1=0`}
      )
      SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
             municipality, subject, party, value, unit, grain, source_code, relative_share
      FROM (
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               municipality, subject, party, value, unit, grain, source_code, relative_share, category_rank
        FROM muni_rows
        UNION ALL BY NAME
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               municipality, subject, party, value, unit, grain, source_code, relative_share, category_rank
        FROM pref_turnout
        UNION ALL BY NAME
        SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
               municipality, subject, party, value, unit, grain, source_code, relative_share, category_rank
        FROM gap_rows
      )
      ORDER BY category_rank,
               municipality DESC NULLS LAST,
               election_kaiji DESC,
               prefecture_code NULLS LAST,
               district_number NULLS LAST,
               value DESC NULLS LAST
      ${limitOffsetSql()}`;
    }
    const core = whereClauseMuniCore();
    const smdExtra = whereClauseMuniSmdExtra();
    const prefWhere = whereClausePrefRelated();
    const keyword = els.keyword.value.trim();
    const keywordSql = keyword
      ? `AND (coalesce(CAST(metric AS VARCHAR), '') ILIKE '%${escapeSql(keyword)}%' OR coalesce(justice, '') ILIKE '%${escapeSql(keyword)}%')`
      : '';
    // Prefer exact municipality match; if none selected, show municipality-grain rows under filters.
    const districtCat = state.chamber === 'sangiin' ? '選挙区' : '小選挙区';
    const turnoutContest = state.chamber === 'sangiin' ? 'district' : 'smd';
    const showPrefRelated = state.chamber === 'shugiin';
    const yomiJoin = state.chamber === 'sangiin' ? sangiinYomiMuniJoinSql('m') : '';
    const subjectExpr = (state.chamber === 'sangiin' && state.hasSangiinYomiNameMap)
      ? 'coalesce(ym.yomi_name, m.subject)'
      : 'm.subject';
    return `
      WITH muni_base AS (
        SELECT *
        FROM read_parquet('municipality_facts.parquet')
        WHERE ${core || '1=1'}
          AND (category = '比例代表' OR (category = '${districtCat}'${smdExtra}))
      ),
      muni_rows AS (
        SELECT m.election_kaiji, m.category, m.prefecture, m.prefecture_code, m.district_number,
               ${municipalityNormSql('m.municipality')} AS municipality, ${subjectExpr} AS subject, m.party, m.value, m.unit, m.grain, m.source_code,
               CASE
                 WHEN m.category IN ('小選挙区', '選挙区', '比例代表')
                   AND sum(m.value) OVER (
                     PARTITION BY m.election_kaiji, m.category, m.prefecture, ${municipalityNormSql('m.municipality')}, m.metric
                   ) > 0
                 THEN 100.0 * m.value / sum(m.value) OVER (
                   PARTITION BY m.election_kaiji, m.category, m.prefecture, ${municipalityNormSql('m.municipality')}, m.metric
                 )
                 ELSE NULL
               END AS relative_share,
               CASE m.category
                 WHEN '小選挙区' THEN 0
                 WHEN '選挙区' THEN 0
                 WHEN '比例代表' THEN 1
                 ELSE 9
               END AS category_rank
        FROM muni_base m
        ${yomiJoin}
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
               NULL::DOUBLE AS relative_share,
               2 AS category_rank
        FROM read_parquet('facts.parquet')
        WHERE contest = '${turnoutContest}'
          AND metric IN ('eligible_voters', 'voters', 'turnout_rate')
          AND (scope = 'all' OR scope IS NULL)
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          AND ${chamberSql()}
          ${prefWhere ? `AND ${prefWhere}` : ''}
          ${keywordSql}
          ${els.municipality.value || els.prefecture.value ? '' : 'AND 1=0'}
          ${showPrefRelated ? '' : 'AND 1=0'}
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
               NULL::DOUBLE AS relative_share,
               3 AS category_rank
        FROM read_parquet('facts.parquet')
        WHERE contest = 'judicial_review'
          AND metric IN ('dismissal_yes', 'dismissal_no')
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          AND ${chamberSql()}
          ${prefWhere ? `AND ${prefWhere}` : ''}
          ${keywordSql}
          ${els.municipality.value || els.prefecture.value ? '' : 'AND 1=0'}
          ${showPrefRelated ? '' : 'AND 1=0'}
      )
      SELECT election_kaiji, category, prefecture, prefecture_code, district_number,
             municipality, subject, party, value, unit, grain, source_code, relative_share
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
      ${limitOffsetSql()}`;
  }

  if (state.tab === 'pr') {
    normalizeSeijiPrGeoLevel();
    const level = els.geoLevel.value;
    const partyFilter = partyFilterSql();
    const partyNotTotal = `AND coalesce(party, '') <> '合計' AND coalesce(party, '') <> '計'`;
    const electionFilter = els.election.value ? `AND election_kaiji = ${Number(els.election.value)}` : '';
    const blockFilter = els.prBlock.value
      ? `AND replace(pr_block, '選挙区', '') = '${escapeSql(els.prBlock.value)}'`
      : '';
    const prefFilter = els.prefecture.value ? `AND prefecture = '${escapeSql(els.prefecture.value)}'` : '';

    if (usesSeijiSource() || (usesUnifiedSource() && (level === 'national' || level === 'block'))) {
      // 都道府県粒は無い → 全国以外はブロック（政治学会のみ）
      const geo = (level === 'national') ? 'national' : 'block';
      const seijiBlockFilter = els.prBlock.value
        ? `AND pr_block = '${escapeSql(els.prBlock.value)}'`
        : '';
      // 相対得票率は全区政党で計算し、政党フィルタは外側で適用する
      const seijiNationalInner = `
          SELECT election_kaiji, '全国' AS pr_block, party, value, unit, source_code,
            CASE WHEN sum(value) OVER (PARTITION BY election_kaiji) > 0
              THEN 100.0 * value / sum(value) OVER (PARTITION BY election_kaiji)
              ELSE NULL END AS relative_share,
            NULL::DOUBLE AS absolute_share
          FROM read_parquet('seiji_gakkai_pr_votes.parquet')
          WHERE metric = 'party_votes' AND geo_level = 'national'
            ${electionFilter} ${partyNotTotal}`;
      const seijiBlockInner = `
        SELECT election_kaiji, pr_block, party, value, unit, source_code,
          CASE WHEN sum(value) OVER (PARTITION BY election_kaiji, pr_block) > 0
            THEN 100.0 * value / sum(value) OVER (PARTITION BY election_kaiji, pr_block)
            ELSE NULL END AS relative_share,
          CASE WHEN coalesce(block_eligible_voters, 0) > 0
            THEN 100.0 * value / block_eligible_voters
            ELSE NULL END AS absolute_share
        FROM read_parquet('seiji_gakkai_pr_votes.parquet')
        WHERE metric = 'party_votes' AND geo_level = 'block'
          ${electionFilter} ${seijiBlockFilter} ${partyNotTotal}`;

      if (usesSeijiSource()) {
        if (geo === 'national') {
          return `
          SELECT * FROM (${seijiNationalInner}) scored
          WHERE 1=1 ${partyFilter}
          ORDER BY election_kaiji DESC, value DESC NULLS LAST, party
          ${limitOffsetSql()}`;
        }
        return `
        SELECT * FROM (${seijiBlockInner}) scored
        WHERE 1=1 ${partyFilter}
        ORDER BY election_kaiji DESC, pr_block, value DESC NULLS LAST, party
        ${limitOffsetSql()}`;
      }

      // 統合: MIC + 政治学会穴埋め（同一回が MIC にあれば政治学会は出さない）
      if (geo === 'national') {
        return `
          WITH mic AS (
            SELECT election_kaiji, '全国' AS pr_block, party, value, unit, source_code,
              CASE WHEN sum(value) OVER (PARTITION BY election_kaiji) > 0
                THEN 100.0 * value / sum(value) OVER (PARTITION BY election_kaiji)
                ELSE NULL END AS relative_share,
              NULL::DOUBLE AS absolute_share
            FROM read_parquet('facts.parquet')
            WHERE ${chamberSql()}
              AND metric = 'current_votes' AND contest = 'pr' AND source_code = '03-05'
              ${partyNotTotal} ${electionFilter}
              AND coalesce(party, '') NOT IN ('合計', '計', '諸派')
          ),
          seiji AS (
            ${seijiNationalInner}
              AND election_kaiji NOT IN (SELECT DISTINCT election_kaiji FROM mic)
          ),
          combined AS (
            SELECT election_kaiji, pr_block, party, value, unit, source_code, relative_share, absolute_share FROM mic
            UNION ALL
            SELECT election_kaiji, pr_block, party, value, unit, source_code, relative_share, absolute_share FROM seiji
          )
          SELECT * FROM combined
          WHERE 1=1 ${partyFilter}
          ORDER BY election_kaiji DESC, value DESC NULLS LAST, party
          ${limitOffsetSql()}`;
      }
      // ブロック: MIC は 03-10（集計）、欠落回のみ政治学会 SH-B
      return `
        WITH mic_votes AS (
          SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block, party,
                 max(value) AS value, any_value(unit) AS unit, any_value(source_code) AS source_code
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
            ${electionFilter} ${blockFilter} ${partyNotTotal}
          GROUP BY election_kaiji, replace(pr_block, '選挙区', ''), party
        ),
        mic AS (
          SELECT v.election_kaiji, v.pr_block, v.party, v.value, v.unit, v.source_code,
            CASE WHEN sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block) > 0
              THEN 100.0 * v.value / sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block)
              ELSE NULL END AS relative_share,
            NULL::DOUBLE AS absolute_share
          FROM mic_votes v
        ),
        seiji AS (
          ${seijiBlockInner}
            AND election_kaiji NOT IN (SELECT DISTINCT election_kaiji FROM mic)
        ),
        combined AS (
          SELECT election_kaiji, pr_block, party, value, unit, source_code, relative_share, absolute_share FROM mic
          UNION ALL
          SELECT election_kaiji, pr_block, party, value, unit, source_code, relative_share, absolute_share FROM seiji
        )
        SELECT * FROM combined
        WHERE 1=1 ${partyFilter}
        ORDER BY election_kaiji DESC, pr_block, value DESC NULLS LAST, party
        ${limitOffsetSql()}`;
    }

    if (level === 'national') {
      const sourceFilter = state.chamber === 'sangiin'
        ? ``
        : `AND source_code = '03-05'`;
      return `
        WITH votes AS (
          SELECT election_kaiji, party, value, unit, source_code
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND metric = 'current_votes' AND contest = 'pr' ${sourceFilter}
            ${partyNotTotal} ${electionFilter}
            AND coalesce(party, '') NOT IN ('合計', '計', '諸派')
        ),
        eligible AS (
          SELECT election_kaiji, sum(value) AS eligible_voters
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND contest = 'pr' AND metric = 'eligible_voters'
            AND gender = 'total' AND (scope = 'all' OR scope IS NULL)
            AND coalesce(pr_block, '') <> ''
          GROUP BY election_kaiji
        ),
        scored AS (
          SELECT v.election_kaiji, '全国' AS pr_block, v.party, v.value, v.unit, v.source_code,
            CASE WHEN sum(v.value) OVER (PARTITION BY v.election_kaiji) > 0
              THEN 100.0 * v.value / sum(v.value) OVER (PARTITION BY v.election_kaiji)
              ELSE NULL END AS relative_share,
            CASE WHEN e.eligible_voters > 0 THEN 100.0 * v.value / e.eligible_voters ELSE NULL END AS absolute_share
          FROM votes v
          LEFT JOIN eligible e ON v.election_kaiji = e.election_kaiji
        )
        SELECT * FROM scored
        WHERE 1=1 ${partyFilter}
        ORDER BY election_kaiji DESC, value DESC NULLS LAST
        ${limitOffsetSql()}`;
    }

    if (level === 'block') {
      if (state.chamber === 'sangiin') {
        return `
          SELECT election_kaiji, '—' AS pr_block, party, value, unit, source_code,
                 NULL::DOUBLE AS relative_share, NULL::DOUBLE AS absolute_share
          FROM read_parquet('facts.parquet')
          WHERE 1=0 ${limitOffsetSql()}`;
      }
      return `
        WITH votes AS (
          SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block, party,
                 max(value) AS value, any_value(unit) AS unit, any_value(source_code) AS source_code
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
            ${electionFilter} ${blockFilter} ${partyNotTotal}
          GROUP BY election_kaiji, replace(pr_block, '選挙区', ''), party
        ),
        eligible AS (
          SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block, sum(value) AS eligible_voters
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND contest = 'pr' AND metric = 'eligible_voters' AND source_code = '02-02'
            AND gender = 'total' AND (scope = 'all' OR scope IS NULL)
            AND coalesce(pr_block, '') <> ''
          GROUP BY election_kaiji, replace(pr_block, '選挙区', '')
        ),
        scored AS (
          SELECT v.*,
            CASE WHEN sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block) > 0
              THEN 100.0 * v.value / sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block)
              ELSE NULL END AS relative_share,
            CASE WHEN e.eligible_voters > 0 THEN 100.0 * v.value / e.eligible_voters ELSE NULL END AS absolute_share
          FROM votes v
          LEFT JOIN eligible e ON v.election_kaiji = e.election_kaiji AND v.pr_block = e.pr_block
        )
        SELECT * FROM scored
        WHERE 1=1 ${partyFilter}
        ORDER BY election_kaiji DESC, value DESC NULLS LAST
        ${limitOffsetSql()}`;
    }

    if (level === 'list') {
      const keywordParts = [
        keywordCompactSql('candidate'),
        keywordCompactSql('candidate_raw'),
        keywordCompactSql('party')
      ].filter(Boolean);
      const keywordSql = keywordParts.length ? `AND (${keywordParts.join(' OR ')})` : '';
      if (state.chamber === 'shugiin') {
        return `
          SELECT election_kaiji,
                 replace(pr_block, '選挙区', '') AS pr_block,
                 party,
                 value AS list_rank,
                 candidate,
                 candidate_raw,
                 NULL::DOUBLE AS value,
                 '順位' AS unit,
                 source_code,
                 NULL::BOOLEAN AS elected
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND source_code = '03-11' AND metric = 'pr_list_position'
            AND candidate IS NOT NULL
            ${electionFilter} ${blockFilter} ${partyFilter} ${keywordSql}
          ORDER BY election_kaiji DESC, pr_block NULLS LAST, party, list_rank
          ${limitOffsetSql()}`;
      }
      if (els.prefecture.value) {
        return `
          SELECT election_kaiji, prefecture, prefecture_code, party,
                 candidate, candidate_raw, elected, value, unit, source_code
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND metric = 'candidate_votes' AND contest = 'pr'
            AND prefecture IS NOT NULL
            AND prefecture NOT IN ('計', '合計', '全国')
            ${electionFilter} ${prefFilter} ${partyFilter} ${keywordSql}
          ORDER BY election_kaiji DESC, value DESC NULLS LAST, party, candidate
          ${limitOffsetSql()}`;
      }
      return `
        SELECT election_kaiji, party, candidate, candidate_raw, elected, value, unit, source_code
        FROM read_parquet('facts.parquet')
        WHERE ${chamberSql()}
          AND metric = 'candidate_votes' AND contest = 'pr'
          AND prefecture IS NULL
          ${electionFilter} ${partyFilter} ${keywordSql}
        ORDER BY election_kaiji DESC, value DESC NULLS LAST, party, candidate
        ${limitOffsetSql()}`;
    }

    if (state.chamber === 'sangiin') {
      return `
        WITH votes AS (
          SELECT election_kaiji, '比例' AS pr_block,
                 prefecture, any_value(prefecture_code) AS prefecture_code, party,
                 max(value) AS value,
                 any_value(unit) AS unit, any_value(source_code) AS source_code
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND metric = 'party_votes' AND contest = 'pr'
            AND prefecture IS NOT NULL
            AND prefecture NOT IN ('計', '合計', '全国')
            AND source_code = '03-05'
            ${electionFilter} ${prefFilter} ${partyNotTotal}
          GROUP BY election_kaiji, prefecture, party
        ),
        eligible AS (
          SELECT election_kaiji, prefecture, max(value) AS eligible_voters
          FROM read_parquet('facts.parquet')
          WHERE ${chamberSql()}
            AND contest = 'pr' AND metric = 'eligible_voters'
            AND gender = 'total' AND (scope = 'all' OR scope IS NULL)
            AND prefecture IS NOT NULL
          GROUP BY election_kaiji, prefecture
        ),
        scored AS (
          SELECT v.*,
            CASE WHEN sum(v.value) OVER (PARTITION BY v.election_kaiji, v.prefecture) > 0
              THEN 100.0 * v.value / sum(v.value) OVER (PARTITION BY v.election_kaiji, v.prefecture)
              ELSE NULL END AS relative_share,
            CASE WHEN e.eligible_voters > 0 THEN 100.0 * v.value / e.eligible_voters ELSE NULL END AS absolute_share
          FROM votes v
          LEFT JOIN eligible e ON v.election_kaiji = e.election_kaiji AND v.prefecture = e.prefecture
        )
        SELECT * FROM scored
        WHERE 1=1 ${partyFilter}
        ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, value DESC NULLS LAST
        ${limitOffsetSql()}`;
    }

    return `
      WITH votes AS (
        SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block,
               prefecture, any_value(prefecture_code) AS prefecture_code, party,
               max(value) AS value,
               any_value(unit) AS unit, any_value(source_code) AS source_code
        FROM read_parquet('facts.parquet')
        WHERE ${chamberSql()}
          AND metric = 'party_votes' AND contest = 'pr' AND source_code = '03-07'
          AND prefecture IS NOT NULL
          AND prefecture NOT IN ('計', '合計', '全国')
          ${electionFilter} ${blockFilter} ${prefFilter} ${partyNotTotal}
        GROUP BY election_kaiji, replace(pr_block, '選挙区', ''), prefecture, party
      ),
      eligible AS (
        SELECT election_kaiji, prefecture, max(value) AS eligible_voters
        FROM read_parquet('facts.parquet')
        WHERE ${chamberSql()}
          AND contest = 'pr' AND metric = 'eligible_voters'
          AND gender = 'total' AND (scope = 'all' OR scope IS NULL)
          AND prefecture IS NOT NULL
        GROUP BY election_kaiji, prefecture
      ),
      scored AS (
        SELECT v.*,
          CASE WHEN sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block, v.prefecture) > 0
            THEN 100.0 * v.value / sum(v.value) OVER (PARTITION BY v.election_kaiji, v.pr_block, v.prefecture)
            ELSE NULL END AS relative_share,
          CASE WHEN e.eligible_voters > 0 THEN 100.0 * v.value / e.eligible_voters ELSE NULL END AS absolute_share
        FROM votes v
        LEFT JOIN eligible e ON v.election_kaiji = e.election_kaiji AND v.prefecture = e.prefecture
      )
      SELECT * FROM scored
      WHERE 1=1 ${partyFilter}
      ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, value DESC NULLS LAST
      ${limitOffsetSql()}`;
  }

  if (state.tab === 'prlist') {
    if (state.chamber === 'sangiin') {
      const partyFilter = partyFilterSql();
      const electionFilter = els.election.value
        ? `AND election_kaiji = ${Number(els.election.value)}`
        : '';
      const electedFilter = els.electedFilter?.value === 'won'
        ? `AND elected = true`
        : (els.electedFilter?.value === 'lost' ? `AND elected = false` : '');
      const keywordParts = [
        keywordCompactSql('candidate'),
        keywordCompactSql('candidate_raw'),
        keywordCompactSql('party')
      ].filter(Boolean);
      const keywordSql = keywordParts.length ? `AND (${keywordParts.join(' OR ')})` : '';
      return `
        SELECT election_kaiji, party, candidate, candidate_raw, elected, value, unit, source_code,
               CASE WHEN elected THEN 'pr' WHEN elected = false THEN 'loss' ELSE NULL END AS outcome
        FROM read_parquet('facts.parquet')
        WHERE election_id LIKE 'sangiin-%'
          AND contest = 'pr' AND metric = 'candidate_votes'
          AND prefecture IS NULL
          AND candidate IS NOT NULL
          ${electionFilter} ${partyFilter} ${electedFilter} ${keywordSql}
        ORDER BY election_kaiji DESC, value DESC NULLS LAST, party, candidate
        ${limitOffsetSql()}`;
    }
    if (!state.hasYomiPrMeibo) {
      return `SELECT 1 WHERE 1=0 ${limitOffsetSql()}`;
    }
    const partyFilter = partyFilterSql();
    const electionFilter = els.election.value
      ? `AND election_kaiji = ${Number(els.election.value)}`
      : '';
    const blockFilter = els.prBlock.value
      ? `AND pr_block = '${escapeSql(els.prBlock.value)}'`
      : '';
    const electedRaw = els.electedFilter?.value || '';
    const electedFilter = ['pr', 'smd', 'loss'].includes(electedRaw)
      ? `AND outcome = '${electedRaw}'`
      : '';
    const keywordParts = [
      keywordCompactSql('candidate'),
      keywordCompactSql('party'),
      keywordCompactSql('party_short'),
      keywordPersonAliasSql('candidate', 'candidate')
    ].filter(Boolean);
    const keywordSql = keywordParts.length ? `AND (${keywordParts.join(' OR ')})` : '';
    return `
      SELECT election_kaiji, pr_block, party, party_short, list_rank, candidate,
             party_seats, sekihai_rate, dual_district, result_status, outcome, source,
             ${personCanonicalJoinSql('candidate')}
      FROM read_parquet('yomi_pr_meibo.parquet')
      WHERE candidate IS NOT NULL AND candidate <> ''
        ${electionFilter} ${blockFilter} ${partyFilter} ${electedFilter} ${keywordSql}
      ORDER BY election_kaiji DESC, pr_block NULLS LAST, party, list_rank,
               coalesce(sekihai_rate, -1) DESC, candidate
      ${limitOffsetSql()}`;
  }

  if (state.tab === 'turnout') {
    if (usesSeijiSource() || usesUnifiedSource()) {
      const parts = [`metric = '${escapeSql(els.metric.value)}'`];
      if (els.contest.value) parts.push(`contest = '${escapeSql(els.contest.value)}'`);
      if (els.election.value) parts.push(`election_kaiji = ${Number(els.election.value)}`);
      if (els.scope.value === 'all') parts.push(`(scope = 'all' OR scope IS NULL)`);
      else if (els.scope.value) parts.push(`scope = '${escapeSql(els.scope.value)}'`);
      if (els.gender && els.gender.value) parts.push(`gender = '${escapeSql(els.gender.value)}'`);
      const region = els.prefecture.value;
      if (region) {
        if (els.contest.value === 'pr') {
          parts.push(`pr_block = '${escapeSql(region)}'`);
        } else if (els.contest.value === 'smd') {
          parts.push(`(prefecture = '${escapeSql(region)}' OR (grain IN ('district', 'municipality') AND prefecture = '${escapeSql(region)}'))`);
        } else {
          parts.push(`(prefecture = '${escapeSql(region)}' OR pr_block = '${escapeSql(region)}')`);
        }
      }
      const seijiSql = `SELECT election_kaiji, contest, scope,
        coalesce(prefecture, pr_block) AS prefecture,
        prefecture_code, metric, gender, value, unit, source_code, pr_block, grain,
        district_number, district_name, municipality
        FROM read_parquet('seiji_gakkai_turnout.parquet')
        WHERE ${parts.join(' AND ')}`;

      if (usesSeijiSource()) {
        return `${seijiSql}
        ORDER BY election_kaiji DESC, contest NULLS LAST,
                 prefecture_code NULLS LAST, pr_block NULLS LAST,
                 CASE grain WHEN 'national' THEN 0 WHEN 'block' THEN 1 WHEN 'prefecture' THEN 2 WHEN 'district' THEN 3 ELSE 4 END,
                 district_number NULLS LAST, municipality NULLS LAST,
                 CASE gender WHEN 'total' THEN 0 WHEN 'male' THEN 1 WHEN 'female' THEN 2 ELSE 3 END
        ${limitOffsetSql()}`;
      }

      return `
        WITH mic AS (
          SELECT election_kaiji, contest, scope, prefecture, prefecture_code,
            metric, gender, value, unit, source_code,
            CAST(NULL AS VARCHAR) AS pr_block,
            'prefecture' AS grain,
            CAST(NULL AS INTEGER) AS district_number,
            CAST(NULL AS VARCHAR) AS district_name,
            CAST(NULL AS VARCHAR) AS municipality
          FROM read_parquet('facts.parquet') WHERE ${whereClauseTurnout()}
        ),
        seiji AS (
          ${seijiSql}
            AND (
              grain IN ('district', 'municipality')
              OR NOT EXISTS (
                SELECT 1 FROM mic m
                WHERE m.election_kaiji = election_kaiji
                  AND m.contest = contest
                  AND m.metric = metric
                  AND (
                    (m.prefecture IS NOT NULL AND m.prefecture = prefecture)
                    OR (contest = 'pr' AND m.prefecture IS NULL)
                  )
              )
            )
        )
        SELECT * FROM (SELECT * FROM mic UNION ALL BY NAME SELECT * FROM seiji)
        ORDER BY election_kaiji DESC, contest NULLS LAST,
                 prefecture_code NULLS LAST, pr_block NULLS LAST,
                 CASE grain WHEN 'national' THEN 0 WHEN 'block' THEN 1 WHEN 'prefecture' THEN 2 WHEN 'district' THEN 3 ELSE 4 END,
                 district_number NULLS LAST, municipality NULLS LAST,
                 CASE gender WHEN 'total' THEN 0 WHEN 'male' THEN 1 WHEN 'female' THEN 2 ELSE 3 END
        ${limitOffsetSql()}`;
    }
    return `SELECT election_kaiji, contest, scope, prefecture, prefecture_code,
      metric, gender, value, unit, source_code
      FROM read_parquet('facts.parquet') WHERE ${whereClauseTurnout()}
      ORDER BY election_kaiji DESC, contest NULLS LAST,
               CASE scope WHEN 'all' THEN 0 WHEN 'overseas' THEN 1 ELSE 2 END,
               prefecture_code NULLS LAST,
               CASE gender WHEN 'total' THEN 0 WHEN 'male' THEN 1 WHEN 'female' THEN 2 ELSE 3 END
      ${limitOffsetSql()}`;
  }

  return `SELECT election_kaiji, prefecture, prefecture_code, justice,
    metric, value, unit, source_code
    FROM read_parquet('facts.parquet') WHERE ${whereClauseJudicial()}
    ORDER BY election_kaiji DESC, prefecture_code NULLS LAST, justice NULLS LAST, value DESC NULLS LAST
    ${limitOffsetSql()}`;
}

function countSql() {
  const sql = selectSql().replace(/\s+LIMIT\s+\d+\s+OFFSET\s+\d+\s*$/i, '');
  return `SELECT count(*) AS count FROM (${sql})`;
}

/** 同一選挙回内の帯分けキー（選挙区・県区・市区町村・ブロックなど） */
function rowBandSubdivisionKey(row) {
  if (state.tab === 'smd') {
    if (state.chamber === 'sangiin') return `pref:${row.prefecture ?? ''}`;
    return `dist:${row.prefecture ?? ''}|${row.district_number ?? ''}`;
  }
  if (state.tab === 'muni') {
    if (row.district_number != null && row.district_number !== '') {
      return `dist:${row.prefecture ?? ''}|${row.district_number}`;
    }
    return `muni:${row.prefecture ?? ''}|${row.municipality ?? ''}|${row.category ?? ''}`;
  }
  if (state.tab === 'pr') {
    const level = els.geoLevel?.value;
    if (level === 'block' || (level === 'list' && state.chamber === 'shugiin')) {
      return `block:${normalizeBlock(row.pr_block) ?? ''}`;
    }
    if (row.prefecture) return `pref:${row.prefecture}`;
    return `party:${row.party ?? ''}`;
  }
  if (state.tab === 'prlist') {
    return `block:${normalizeBlock(row.pr_block) ?? ''}|${row.party ?? ''}`;
  }
  if (state.tab === 'turnout' || state.tab === 'judicial') {
    return `pref:${row.prefecture ?? ''}`;
  }
  return `row`;
}

/**
 * 結果行の背景帯クラス。
 * 選挙回が2つ以上 → 選挙回で帯分け。すべて同一 → 選挙区等で帯分け。
 */
function buildRowBandClasses(rows) {
  const electionKeys = new Set(rows.map((row) => String(row.election_kaiji ?? '')));
  const useElection = electionKeys.size > 1;
  let bandIndex = -1;
  let prevKey = null;
  return rows.map((row) => {
    const key = useElection
      ? `el:${row.election_kaiji ?? ''}`
      : rowBandSubdivisionKey(row);
    if (key !== prevKey) {
      bandIndex += 1;
      prevKey = key;
    }
    return bandIndex % 2 === 1 ? 'row-band-alt' : '';
  });
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
      // DuckDB-Wasm は BIGINT を BigInt で返すため、比較は Number 化してから行う
      const kaijiDiff = Number(b.election_kaiji) - Number(a.election_kaiji);
      if (kaijiDiff) return kaijiDiff;
      const br = (PR_BLOCK_RANK[normalizeBlock(a.pr_block)] ?? 999) - (PR_BLOCK_RANK[normalizeBlock(b.pr_block)] ?? 999);
      if (br) return br;
      const pr = (PREFECTURE_RANK[a.prefecture] ?? 999) - (PREFECTURE_RANK[b.prefecture] ?? 999);
      if (pr) return pr;
      return Number(b.value ?? 0) - Number(a.value ?? 0);
    });
  }

  const bands = buildRowBandClasses(sorted);
  const tr = (index) => (bands[index] ? `<tr class="${bands[index]}">` : '<tr>');

  if (state.tab === 'smd') {
    if (state.chamber === 'sangiin') {
      const showSource = showsSourceColumn();
      els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
        <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
        <td>${html(row.prefecture)}</td>
        <td>${html(districtLabel(row.district_number))}</td>
        <td>${html(displayNameFromRow(row))}</td>
        <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
        <td>${html(electedLabel(row.elected))}</td>
        <td class="numeric">${formatValue(row.value, row.unit)}</td>
        <td class="numeric">${html(formatPercent(row.relative_share))}</td>
        <td class="numeric">${html(formatPercent(row.absolute_share))}</td>
        ${showSource ? `<td>${html(sourceLabel(row.source_code))}</td>` : ''}</tr>`).join('');
      return;
    }
    if (usesSeijiSource() || usesUnifiedSource()) {
      els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
        <td>${html(electionLabelForUi(row.election_kaiji, state.chamber))}</td>
        <td>${html(row.prefecture)}</td>
        <td>${html(districtLabel(row.district_number))}</td>
        <td>${html(displayPersonName(row.candidate, row.candidate_raw, row.canonical_name))}</td>
        <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
        <td>${html(
          row.outcome_label
            || (row.elected_smd === true || row.elected_smd === 'true' ? '当選（小）' : null)
            || (row.elected === true || row.elected === 'true' ? '当選' : null)
            || (row.elected === false || row.elected === 'false' ? '落選' : null)
            || '—'
        )}</td>
        <td class="numeric">${formatValue(row.value, row.unit)}</td>
        <td class="numeric">${html(formatPercent(row.relative_share))}</td>
        <td class="numeric">${html(formatPercent(row.absolute_share))}</td>
        <td class="numeric">${html(formatSekihai(row.sekihai_rate, row.elected_smd ?? row.elected))}</td>
        <td>${html(sourceLabel(row.source_code))}</td></tr>`).join('');
      return;
    }
    els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
      <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
      <td>${html(row.prefecture)}</td>
      <td>${html(districtLabel(row.district_number))}</td>
      <td>${html(displayPersonName(row.candidate, row.candidate_raw, row.canonical_name))}</td>
      <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
      <td>${html(electedLabel(row.elected))}</td>
      <td class="numeric">${formatValue(row.value, row.unit)}</td>
      <td class="numeric">${html(formatPercent(row.relative_share))}</td>
      <td class="numeric">${html(formatSekihai(row.sekihai_rate, row.elected))}</td>
      <td>${html(genderLabel(row.gender))}</td></tr>`).join('');
    return;
  }

  if (state.tab === 'muni') {
    const grainLabel = (grain) => (grain === 'prefecture' ? '都道府県' : '市区町村');
    const showSource = showsSourceColumn();
    els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
      <td>${html(showSource ? electionLabelForUi(row.election_kaiji, state.chamber) : electionLabel(row.election_kaiji, state.chamber))}</td>
      <td>${html(row.category)}</td>
      <td>${html(row.prefecture)}</td>
      <td>${html(districtLabel(row.district_number))}</td>
      <td>${html(displayLabel(row.municipality))}</td>
      <td>${html(displayLabel(row.subject))}</td>
      <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
      <td class="numeric">${formatValue(row.value, row.unit)}</td>
      <td class="numeric">${html(formatPercent(row.relative_share))}</td>
      <td>${html(row.unit)}</td>
      <td>${html(grainLabel(row.grain))}</td>
      ${showSource ? `<td>${html(sourceLabel(row.source_code))}</td>` : ''}</tr>`).join('');
    return;
  }

  if (state.tab === 'pr') {
    const level = els.geoLevel.value;
    const showSource = showsSourceColumn();
    const srcCell = (row) => (showSource ? `<td>${html(sourceLabel(row.source_code))}</td>` : '');
    els.results.innerHTML = sorted.map((row, i) => {
      const block = normalizeBlock(row.pr_block);
      if (level === 'national') {
        return `${tr(i)}
          <td>${html(electionLabelForUi(row.election_kaiji, state.chamber))}</td>
          <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
          <td class="numeric">${formatValue(row.value, row.unit)}</td>
          <td class="numeric">${html(formatPercent(row.relative_share))}</td>
          <td class="numeric">${html(formatPercent(row.absolute_share))}</td>${srcCell(row)}</tr>`;
      }
      if (level === 'block') {
        return `${tr(i)}
          <td>${html(electionLabelForUi(row.election_kaiji, state.chamber))}</td>
          <td>${html(block)}</td>
          <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
          <td class="numeric">${formatValue(row.value, row.unit)}</td>
          <td class="numeric">${html(formatPercent(row.relative_share))}</td>
          <td class="numeric">${html(formatPercent(row.absolute_share))}</td>${srcCell(row)}</tr>`;
      }
      if (level === 'list') {
        if (state.chamber === 'shugiin') {
          return `${tr(i)}
            <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
            <td>${html(block)}</td>
            <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
            <td class="numeric">${html(row.list_rank ?? '—')}</td>
            <td>${html(displayPersonName(row.candidate, row.candidate_raw))}</td>
            <td class="numeric">${row.value == null ? '—' : formatValue(row.value, row.unit)}</td>
            <td>${html(row.unit || '—')}</td></tr>`;
        }
        const elected = row.elected == null ? '—' : (row.elected ? '当' : '落');
        if (els.prefecture.value) {
          return `${tr(i)}
            <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
            <td>${html(row.prefecture)}</td>
            <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
            <td>${html(displayPersonName(row.candidate, row.candidate_raw))}</td>
            <td>${html(elected)}</td>
            <td class="numeric">${formatValue(row.value, row.unit)}</td>
            <td>${html(row.unit)}</td></tr>`;
        }
        return `${tr(i)}
          <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
          <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
          <td>${html(displayPersonName(row.candidate, row.candidate_raw))}</td>
          <td>${html(elected)}</td>
          <td class="numeric">${formatValue(row.value, row.unit)}</td>
          <td>${html(row.unit)}</td></tr>`;
      }
      if (state.chamber === 'sangiin') {
        return `${tr(i)}
          <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
          <td>${html(row.prefecture)}</td>
          <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
          <td class="numeric">${formatValue(row.value, row.unit)}</td>
          <td class="numeric">${html(formatPercent(row.relative_share))}</td>
          <td class="numeric">${html(formatPercent(row.absolute_share))}</td></tr>`;
      }
      return `${tr(i)}
        <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
        <td>${html(block)}</td>
        <td>${html(row.prefecture)}</td>
        <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
        <td class="numeric">${formatValue(row.value, row.unit)}</td>
        <td class="numeric">${html(formatPercent(row.relative_share))}</td>
        <td class="numeric">${html(formatPercent(row.absolute_share))}</td>${srcCell(row)}</tr>`;
    }).join('');
    return;
  }

  if (state.tab === 'prlist') {
    if (state.chamber === 'sangiin') {
      els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
        <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
        <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
        <td>${html(displayPersonName(row.candidate, row.candidate_raw, row.canonical_name))}</td>
        <td>${html(electedLabel(row.elected))}</td>
        <td class="numeric">${formatValue(row.value, row.unit)}</td>
        <td>${html(sourceLabel(row.source_code))}</td></tr>`).join('');
      return;
    }
    if (!state.hasYomiPrMeibo) {
      els.results.innerHTML = emptyRow(headers.length, '読売紙面の比例名簿データが読み込まれていません。');
      return;
    }
    els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
      <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
      <td>${html(normalizeBlock(row.pr_block))}</td>
      <td>${html(displayPartyName(row.party, row.election_kaiji))}</td>
      <td class="numeric">${html(row.list_rank ?? '—')}</td>
      <td>${html(displayPersonName(row.candidate, null, row.canonical_name))}</td>
      <td>${html(displayLabel(row.dual_district))}</td>
      <td class="numeric">${html(row.party_seats == null ? '—' : displayVotes.format(Number(row.party_seats)))}</td>
      <td class="numeric">${html(formatSekihai(row.sekihai_rate, row.outcome === 'smd'))}</td>
      <td>${html(prListOutcomeLabel(row.outcome))}</td>
      <td>${html(sourceLabel(row.source))}</td></tr>`).join('');
    return;
  }

  if (state.tab === 'turnout') {
    const showSource = showsSourceColumn();
    els.results.innerHTML = sorted.map((row, i) => {
      let region = row.prefecture;
      if (row.grain === 'district' && row.district_name) region = row.district_name;
      else if (row.grain === 'municipality' && row.municipality) {
        region = `${row.prefecture || ''}${row.municipality}`;
      }
      return `${tr(i)}
      <td>${html(electionLabelForUi(row.election_kaiji, state.chamber))}</td>
      <td>${html(contestLabel(row.contest))}</td>
      <td>${html(scopeLabel(row.scope))}</td>
      <td>${html(region)}</td>
      <td>${html(metricLabel(row.metric))}</td>
      <td>${html(genderLabel(row.gender))}</td>
      <td class="numeric">${formatValue(row.value, row.unit)}</td>
      <td>${html(row.unit)}</td>
      ${showSource ? `<td>${html(sourceLabel(row.source_code))}</td>` : ''}</tr>`;
    }).join('');
    return;
  }

  els.results.innerHTML = sorted.map((row, i) => `${tr(i)}
    <td>${html(electionLabel(row.election_kaiji, state.chamber))}</td>
    <td>${html(row.prefecture)}</td>
    <td>${html(displayLabel(row.justice))}</td>
    <td>${html(metricLabel(row.metric))}</td>
    <td class="numeric">${formatValue(row.value, row.unit)}</td>
    <td>${html(row.unit)}</td></tr>`).join('');
}

function csvHeaders() {
  if (state.tab === 'smd') {
    if (state.chamber === 'sangiin') {
      return [
        'election_label', 'election_kaiji', 'election_year', 'prefecture', 'district_number',
        'candidate', 'party', 'elected', 'elected_label', 'value', 'unit',
        'relative_share', 'absolute_share', 'source_code'
      ];
    }
    if (usesSeijiSource()) {
      return [
        'election_label', 'election_kaiji', 'election_year', 'prefecture', 'district_number',
        'candidate', 'party', 'outcome', 'outcome_label', 'value', 'unit',
        'relative_share', 'absolute_share', 'sekihai_rate', 'source_code'
      ];
    }
    return [
      'election_label', 'election_kaiji', 'election_year', 'prefecture', 'district_number',
      'candidate', 'party', 'elected', 'elected_label', 'value', 'unit',
      'relative_share', 'sekihai_rate', 'gender', 'gender_label', 'source_code'
    ];
  }
  if (state.tab === 'muni') {
    return [
      'election_label', 'election_kaiji', 'election_year', 'category', 'prefecture',
      'district_number', 'municipality', 'subject', 'party', 'value', 'relative_share',
      'unit', 'grain', 'source_code'
    ];
  }
  if (state.tab === 'pr') {
    const level = els.geoLevel?.value;
    if (level === 'list') {
      if (state.chamber === 'shugiin') {
        return [
          'election_label', 'election_kaiji', 'election_year', 'geo_level', 'pr_block',
          'party', 'list_rank', 'candidate', 'value', 'unit', 'source_code'
        ];
      }
      return [
        'election_label', 'election_kaiji', 'election_year', 'geo_level', 'prefecture',
        'party', 'candidate', 'elected', 'elected_label', 'value', 'unit', 'source_code'
      ];
    }
    return [
      'election_label', 'election_kaiji', 'election_year', 'geo_level', 'pr_block',
      'prefecture', 'party', 'value', 'unit', 'relative_share', 'absolute_share', 'source_code'
    ];
  }
  if (state.tab === 'prlist') {
    if (state.chamber === 'sangiin') {
      return [
        'election_label', 'election_kaiji', 'election_year', 'party', 'candidate',
        'elected', 'elected_label', 'value', 'unit', 'source_code'
      ];
    }
    return [
      'election_label', 'election_kaiji', 'election_year', 'pr_block', 'party',
      'list_rank', 'candidate', 'dual_district', 'party_seats', 'sekihai_rate',
      'outcome', 'outcome_label', 'source'
    ];
  }
  if (state.tab === 'turnout') {
    return [
      'election_label', 'election_kaiji', 'election_year', 'contest', 'contest_label',
      'scope', 'scope_label', 'prefecture', 'metric', 'metric_label',
      'gender', 'gender_label', 'value', 'unit', 'source_code'
    ];
  }
  return [
    'election_label', 'election_kaiji', 'election_year', 'prefecture', 'justice',
    'metric', 'metric_label', 'value', 'unit', 'source_code'
  ];
}

function csvRowValues(row) {
  const label = electionLabel(row.election_kaiji, state.chamber);
  const year = electionYear(row.election_kaiji, state.chamber);
  const person = displayNameFromRow(row);
  if (state.tab === 'smd') {
    if (state.chamber === 'sangiin') {
      return [
        label, row.election_kaiji, year, row.prefecture, row.district_number,
        person, displayPartyName(row.party, row.election_kaiji), row.elected, electedLabel(row.elected),
        row.value, row.unit, row.relative_share, row.absolute_share, row.source_code
      ];
    }
    if (usesSeijiSource()) {
      return [
        label, row.election_kaiji, year, row.prefecture, row.district_number,
        person, displayPartyName(row.party, row.election_kaiji), row.outcome, row.outcome_label,
        row.value, row.unit, row.relative_share, row.absolute_share, row.sekihai_rate, row.source_code
      ];
    }
    return [
      label, row.election_kaiji, year, row.prefecture, row.district_number,
      person, displayPartyName(row.party, row.election_kaiji), row.elected, electedLabel(row.elected),
      row.value, row.unit, row.relative_share, row.sekihai_rate,
      row.gender, genderLabel(row.gender), row.source_code
    ];
  }
  if (state.tab === 'muni') {
    return [
      label, row.election_kaiji, year, row.category, row.prefecture,
      row.district_number, displayLabel(row.municipality), displayLabel(row.subject),
      displayPartyName(row.party, row.election_kaiji), row.value, row.relative_share, row.unit, row.grain, row.source_code
    ];
  }
  if (state.tab === 'pr') {
    const level = els.geoLevel?.value;
    if (level === 'list') {
      if (state.chamber === 'shugiin') {
        return [
          label, row.election_kaiji, year, level, normalizeBlock(row.pr_block),
          displayPartyName(row.party, row.election_kaiji), row.list_rank, person, row.value, row.unit, row.source_code
        ];
      }
      return [
        label, row.election_kaiji, year, level, row.prefecture,
        displayPartyName(row.party, row.election_kaiji), person, row.elected, electedLabel(row.elected),
        row.value, row.unit, row.source_code
      ];
    }
    return [
      label, row.election_kaiji, year, level, normalizeBlock(row.pr_block),
      row.prefecture, displayPartyName(row.party, row.election_kaiji), row.value, row.unit,
      row.relative_share, row.absolute_share, row.source_code
    ];
  }
  if (state.tab === 'prlist') {
    if (state.chamber === 'sangiin') {
      return [
        label, row.election_kaiji, year, displayPartyName(row.party, row.election_kaiji), person,
        row.elected, electedLabel(row.elected), row.value, row.unit, row.source_code
      ];
    }
    return [
      label, row.election_kaiji, year, normalizeBlock(row.pr_block), displayPartyName(row.party, row.election_kaiji),
      row.list_rank, person, displayLabel(row.dual_district), row.party_seats, row.sekihai_rate,
      row.outcome, prListOutcomeLabel(row.outcome), row.source
    ];
  }
  if (state.tab === 'turnout') {
    return [
      label, row.election_kaiji, year, row.contest, contestLabel(row.contest),
      row.scope, scopeLabel(row.scope), row.prefecture, row.metric, metricLabel(row.metric),
      row.gender, genderLabel(row.gender), row.value, row.unit, row.source_code
    ];
  }
  return [
    label, row.election_kaiji, year, row.prefecture, displayLabel(row.justice),
    row.metric, metricLabel(row.metric), row.value, row.unit, row.source_code
  ];
}

function selectSqlAllMatches() {
  return selectSql().replace(/\s+LIMIT\s+\d+\s+OFFSET\s+\d+\s*$/i, '');
}

async function downloadCsv() {
  if (!state.ready || !els.download) return;
  if (!state.matchTotal) {
    els.download.disabled = true;
    return;
  }
  const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  els.download.disabled = true;
  const prevLabel = els.download.textContent;
  els.download.textContent = 'CSV作成中…';
  try {
    const result = await state.conn.query(selectSqlAllMatches());
    const rows = result.toArray().map((row) => row.toJSON());
    const headers = csvHeaders();
    const csv = `\uFEFF${[headers.join(','), ...rows.map((row) => csvRowValues(row).map(quote).join(','))].join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `soumu-election-${state.chamber}-${state.tab}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error(error);
    window.alert('CSVの作成に失敗しました。条件を絞って再試行してください。');
  } finally {
    els.download.textContent = prevLabel || 'CSVを保存 ↓';
    els.download.disabled = !(Number(state.matchTotal) > 0);
  }
}

async function runSearch(event, { resetPage = true } = {}) {
  event?.preventDefault();
  if (!state.ready) return;
  if (resetPage) state.page = 1;
  normalizeSeijiPrGeoLevel();
  if (state.tab === 'muni' && usesSeijiSource() && !state.hasSeijiSmdMuni) {
    els.results.innerHTML = emptyRow(currentHeaders().length, '政治学会の市区町村データが読み込まれていません。');
    return;
  }
  if (state.tab === 'muni' && !usesSeijiSource() && !state.hasMunicipality) {
    els.results.innerHTML = emptyRow(currentHeaders().length, '市区町村データが読み込まれていません。');
    updatePager();
    if (els.download) els.download.disabled = true;
    return;
  }
  const headers = currentHeaders();
  els.head.innerHTML = headers.map((h) => (
    h === '得票' || h === '値' || h === '相対得票率' || h === '絶対得票率' || h === '惜敗率'
      || h === '名簿順位' || h === '当選枠'
      ? `<th class="numeric">${h}</th>`
      : `<th>${h}</th>`
  )).join('');
  els.form.dataset.geolevel = els.geoLevel.value || 'prefecture';
  els.search.disabled = true;
  els.search.textContent = '検索中…';
  if (els.pagePrev) els.pagePrev.disabled = true;
  if (els.pageNext) els.pageNext.disabled = true;
  try {
    const [summary, result] = await Promise.all([
      state.conn.query(countSql()),
      state.conn.query(selectSql())
    ]);
    const totals = summary.toArray()[0].toJSON();
    state.matchTotal = Number(totals.count) || 0;
    const pages = pageCount(state.matchTotal);
    let fetched = result.toArray().map((row) => row.toJSON());
    if (state.page > pages) {
      state.page = pages;
      fetched = (await state.conn.query(selectSql())).toArray().map((row) => row.toJSON());
    }
    state.rows = fetched;
    updatePager();
    const tab = TABS[state.tab];
    const metric = tab.fixedMetric || els.metric.value;
    const geo = state.tab === 'pr' ? ` / ${GEO_LEVEL_LABELS[els.geoLevel.value]}` : '';
    const title = tab.title;
    els.resultLabel.textContent = `${title}${geo} / ${metricLabel(metric)}`;
    if (els.download) els.download.disabled = state.matchTotal <= 0;

    renderRows();
    els.tableShell?.scrollTo?.({ top: 0 });
  } catch (error) {
    console.error(error);
    state.rows = [];
    state.matchTotal = 0;
    updatePager();
    if (els.download) els.download.disabled = true;
    els.results.innerHTML = emptyRow(headers.length, '検索に失敗しました。条件を変えて再試行してください。');
  } finally {
    els.search.disabled = false;
    els.search.textContent = '検索する';
  }
}


async function loadSeijiCoverage() {
  const distinctNums = async (sql) => {
    const rows = await state.conn.query(sql);
    return rows.toArray().map((r) => Number(Object.values(r.toJSON())[0])).filter((n) => Number.isFinite(n));
  };
  const distinctStrings = async (sql) => {
    const rows = await state.conn.query(sql);
    return rows.toArray().map((r) => String(Object.values(r.toJSON())[0])).filter(Boolean);
  };

  if (state.hasSeijiSmdDistrict) {
    try {
      state.seijiSmdElections = await distinctNums(`
        SELECT DISTINCT election_kaiji
        FROM read_parquet('seiji_gakkai_smd_district_votes.parquet')
        WHERE metric = 'candidate_votes' AND election_kaiji IS NOT NULL
        ORDER BY election_kaiji DESC`);
      state.seijiPrefectures = sortPrefectures(await distinctStrings(`
        SELECT DISTINCT prefecture
        FROM read_parquet('seiji_gakkai_smd_district_votes.parquet')
        WHERE prefecture IS NOT NULL
        ORDER BY prefecture`));
      const districts = await state.conn.query(`
        SELECT DISTINCT prefecture, district_number
        FROM read_parquet('seiji_gakkai_smd_district_votes.parquet')
        WHERE district_number IS NOT NULL AND prefecture IS NOT NULL
        ORDER BY prefecture, district_number`);
      state.seijiDistrictsByPref = {};
      for (const row of districts.toArray()) {
        const item = row.toJSON();
        const pref = String(item.prefecture);
        if (!state.seijiDistrictsByPref[pref]) state.seijiDistrictsByPref[pref] = [];
        state.seijiDistrictsByPref[pref].push(Number(item.district_number));
      }
      const smdPartyRows = await state.conn.query(`
        SELECT election_kaiji, party, max(value) AS votes
        FROM read_parquet('seiji_gakkai_smd_district_votes.parquet')
        WHERE metric = 'candidate_votes'
          AND coalesce(party, '') NOT IN ('', '合計', '計')
        GROUP BY election_kaiji, party
        ORDER BY election_kaiji, votes DESC NULLS LAST, party`);
      state.partiesByElectionSeijiSmd = {};
      for (const row of smdPartyRows.toArray()) {
        const item = row.toJSON();
        const key = `shugiin-${item.election_kaiji}`;
        if (!state.partiesByElectionSeijiSmd[key]) state.partiesByElectionSeijiSmd[key] = [];
        state.partiesByElectionSeijiSmd[key].push(String(item.party));
      }
    } catch (error) {
      console.warn('seiji district coverage skipped', error);
      state.hasSeijiSmdDistrict = false;
    }
  }
  if (state.hasSeijiSmdMuni || state.hasSeijiPrMuni) {
    try {
      const sources = [];
      if (state.hasSeijiSmdMuni) sources.push(`SELECT election_kaiji, prefecture, district_number FROM read_parquet('seiji_gakkai_smd_municipality_votes.parquet')`);
      if (state.hasSeijiPrMuni) sources.push(`SELECT election_kaiji, prefecture, district_number FROM read_parquet('seiji_gakkai_pr_municipality_votes.parquet')`);
      const electionsRows = await state.conn.query(`
        SELECT DISTINCT election_kaiji FROM (${sources.join(' UNION ')})
        WHERE election_kaiji IS NOT NULL
        ORDER BY election_kaiji DESC`);
      const prefRows = await state.conn.query(`
        SELECT DISTINCT prefecture FROM (${sources.join(' UNION ')})
        WHERE prefecture IS NOT NULL`);
      const muniDistricts = await state.conn.query(`
        SELECT DISTINCT prefecture, district_number FROM (${sources.join(' UNION ')})
        WHERE district_number IS NOT NULL AND prefecture IS NOT NULL
        ORDER BY prefecture, district_number`);
      state.seijiMuniElections = electionsRows.toArray().map((r) => Number(r.toJSON().election_kaiji));
      state.seijiMuniPrefectures = sortPrefectures(prefRows.toArray().map((r) => String(r.toJSON().prefecture)));
      const byPref = {};
      for (const row of muniDistricts.toArray()) {
        const item = row.toJSON();
        const pref = String(item.prefecture);
        if (!byPref[pref]) byPref[pref] = [];
        byPref[pref].push(Number(item.district_number));
      }
      state.seijiMuniDistrictsByPref = byPref;
      state.hasSeijiSmdMuni = state.hasSeijiSmdMuni || state.hasSeijiPrMuni;
    } catch (error) {
      console.warn('seiji muni coverage skipped', error);
      state.hasSeijiSmdMuni = false;
    }
  }
  if (state.hasSeijiTurnout) {
    try {
      state.seijiTurnoutElections = await distinctNums(`
        SELECT DISTINCT election_kaiji
        FROM read_parquet('seiji_gakkai_turnout.parquet')
        WHERE election_kaiji IS NOT NULL
        ORDER BY election_kaiji DESC`);
      state.seijiTurnoutPrefectures = sortPrefectures(await distinctStrings(`
        SELECT DISTINCT prefecture
        FROM read_parquet('seiji_gakkai_turnout.parquet')
        WHERE prefecture IS NOT NULL`));
      const blocks = await distinctStrings(`
        SELECT DISTINCT pr_block
        FROM read_parquet('seiji_gakkai_turnout.parquet')
        WHERE contest = 'pr' AND grain = 'block'
          AND pr_block IS NOT NULL AND pr_block <> '全国'
        ORDER BY pr_block`);
      if (blocks.length) state.seijiPrBlocks = blocks;
    } catch (error) {
      console.warn('seiji turnout coverage skipped', error);
      state.hasSeijiTurnout = false;
    }
  }
  if (state.hasSeijiPr) {
    try {
      state.seijiPrElections = await distinctNums(`
        SELECT DISTINCT election_kaiji
        FROM read_parquet('seiji_gakkai_pr_votes.parquet')
        WHERE election_kaiji IS NOT NULL
        ORDER BY election_kaiji DESC`);
      const partyRows = await state.conn.query(`
        SELECT election_kaiji, party, max(value) AS votes
        FROM read_parquet('seiji_gakkai_pr_votes.parquet')
        WHERE geo_level = 'national' AND coalesce(party, '') NOT IN ('', '合計', '計')
        GROUP BY election_kaiji, party
        ORDER BY election_kaiji, votes DESC NULLS LAST, party`);
      state.partiesByElectionSeiji = {};
      for (const row of partyRows.toArray()) {
        const item = row.toJSON();
        const key = `shugiin-${item.election_kaiji}`;
        if (!state.partiesByElectionSeiji[key]) state.partiesByElectionSeiji[key] = [];
        state.partiesByElectionSeiji[key].push(String(item.party));
      }
      const blocks = await distinctStrings(`
        SELECT DISTINCT pr_block
        FROM read_parquet('seiji_gakkai_pr_votes.parquet')
        WHERE geo_level = 'block' AND pr_block IS NOT NULL
        ORDER BY pr_block`);
      if (blocks.length) state.seijiPrBlocks = blocks;
    } catch (error) {
      console.warn('seiji pr coverage skipped', error);
      state.hasSeijiPr = false;
    }
  }
}

async function loadCoverage() {
  const loadFor = async (prefix) => {
    const coverage = await state.conn.query(`
      SELECT
        list_sort(list_distinct(list(election_kaiji) FILTER (
          WHERE metric = 'candidate_votes' AND contest IN ('smd', 'district')
        ))) smd_elections,
        list_sort(list_distinct(list(election_kaiji) FILTER (
          WHERE metric IN ('party_votes', 'current_votes') AND contest IN ('pr', 'district')
        ))) pr_elections,
        list_sort(list_distinct(list(election_kaiji) FILTER (
          WHERE metric = 'pr_list_position'
            OR (metric = 'candidate_votes' AND contest = 'pr' AND prefecture IS NULL)
        ))) prlist_elections,
        list_sort(list_distinct(list(election_kaiji) FILTER (WHERE metric IN ('eligible_voters','voters','turnout_rate')))) turnout_elections,
        list_sort(list_distinct(list(election_kaiji) FILTER (WHERE contest = 'judicial_review'))) judicial_elections,
        list_sort(list_distinct(list(prefecture) FILTER (WHERE prefecture IS NOT NULL))) prefectures,
        count(*) AS fact_count
      FROM read_parquet('facts.parquet')
      WHERE election_id LIKE '${prefix}%'`);
    const values = coverage.toArray()[0].toJSON();
    const toNums = (list) => Array.from(list ?? []).map(Number).sort((a, b) => b - a);
    return {
      smd: toNums(values.smd_elections),
      pr: toNums(values.pr_elections),
      prlist: toNums(values.prlist_elections),
      turnout: toNums(values.turnout_elections),
      judicial: toNums(values.judicial_elections),
      muni: [],
      prefectures: sortPrefectures(Array.from(values.prefectures ?? []).map(String)),
      factCount: Number(values.fact_count ?? 0)
    };
  };

  state.electionsByChamber = {
    shugiin: await loadFor('shugiin-'),
    sangiin: await loadFor('sangiin-')
  };
  state.electionsByTab = state.electionsByChamber.shugiin;
  state.allPrefectures = state.electionsByChamber.shugiin.prefectures;
  state.factCount = state.electionsByChamber.shugiin.factCount + state.electionsByChamber.sangiin.factCount;

  const seatRows = await state.conn.query(`
    SELECT list_sort(list_distinct(list(district_number))) seats
    FROM read_parquet('facts.parquet')
    WHERE election_id LIKE 'sangiin-%'
      AND metric = 'candidate_votes' AND contest = 'district'
      AND district_number IS NOT NULL`);
  const seatList = seatRows.toArray()[0]?.toJSON()?.seats;
  state.seatMagnitudes = Array.from(seatList ?? []).map(Number).sort((a, b) => a - b);

  const districts = await state.conn.query(`
    SELECT prefecture, list_sort(list_distinct(list(district_number))) districts
    FROM read_parquet('facts.parquet')
    WHERE metric = 'candidate_votes' AND contest = 'smd' AND district_number IS NOT NULL
      AND election_id LIKE 'shugiin-%'
    GROUP BY prefecture`);
  state.districtsByPref = {};
  for (const row of districts.toArray()) {
    const item = row.toJSON();
    state.districtsByPref[String(item.prefecture)] = Array.from(item.districts ?? []).map(Number);
  }

  if (state.hasMunicipality) {
    try {
      const loadMuniFor = async (chamberFilter, category) => {
        const electionsRows = await state.conn.query(`
          SELECT DISTINCT election_kaiji
          FROM read_parquet('municipality_facts.parquet')
          WHERE prefecture IS NOT NULL AND ${chamberFilter}
          ORDER BY election_kaiji DESC`);
        const prefRows = await state.conn.query(`
          SELECT DISTINCT prefecture
          FROM read_parquet('municipality_facts.parquet')
          WHERE prefecture IS NOT NULL AND ${chamberFilter}`);
        const muniDistricts = await state.conn.query(`
          SELECT DISTINCT prefecture, district_number
          FROM read_parquet('municipality_facts.parquet')
          WHERE category = '${category}' AND district_number IS NOT NULL AND prefecture IS NOT NULL
            AND ${chamberFilter}
          ORDER BY prefecture, district_number`);
        const byPref = {};
        for (const row of muniDistricts.toArray()) {
          const item = row.toJSON();
          const pref = String(item.prefecture);
          if (!byPref[pref]) byPref[pref] = [];
          byPref[pref].push(Number(item.district_number));
        }
        return {
          elections: electionsRows.toArray().map((r) => Number(r.toJSON().election_kaiji)),
          prefectures: sortPrefectures(prefRows.toArray().map((r) => String(r.toJSON().prefecture))),
          districtsByPref: byPref
        };
      };
      const runMuniCoverage = async () => {
        const shugiinMuni = await loadMuniFor(`(chamber IS NULL OR chamber = 'shugiin')`, '小選挙区');
        const sangiinMuni = await loadMuniFor(`chamber = 'sangiin'`, '選挙区');
        state.electionsByChamber.shugiin.muni = shugiinMuni.elections;
        state.electionsByChamber.sangiin.muni = sangiinMuni.elections;
        state.electionsByTab.muni = shugiinMuni.elections;
        state.muniPrefectures = shugiinMuni.prefectures;
        state.muniPrefecturesByChamber = {
          shugiin: shugiinMuni.prefectures,
          sangiin: sangiinMuni.prefectures
        };
        state.muniDistrictsByPref = shugiinMuni.districtsByPref;
        state.muniDistrictsByChamber = {
          shugiin: shugiinMuni.districtsByPref,
          sangiin: sangiinMuni.districtsByPref
        };
      };
      await withTimeout(runMuniCoverage(), INIT_TIMEOUT_MS, 'municipality coverage');
    } catch (muniCoverageError) {
      console.warn('municipality coverage skipped', muniCoverageError);
      state.hasMunicipality = false;
      state.electionsByTab.muni = [];
      state.muniPrefectures = [];
      state.muniPrefecturesByChamber = { shugiin: [], sangiin: [] };
      state.muniDistrictsByPref = {};
      state.muniDistrictsByChamber = { shugiin: {}, sangiin: {} };
    }
  } else {
    state.electionsByTab.muni = [];
    state.muniPrefectures = [];
    state.muniPrefecturesByChamber = { shugiin: [], sangiin: [] };
    state.muniDistrictsByPref = {};
    state.muniDistrictsByChamber = { shugiin: {}, sangiin: {} };
  }

  fillSelect(els.prBlock, PR_BLOCK_ORDER.filter((b) => b !== '全国').map((v) => ({ value: v, label: v })));

  const partyRows = await state.conn.query(`
    SELECT election_id, election_kaiji, party, max(value) AS votes
    FROM read_parquet('facts.parquet')
    WHERE metric = 'current_votes' AND contest = 'pr'
      AND coalesce(party, '') NOT IN ('', '合計', '計', '諸派')
      AND (
        (election_id LIKE 'shugiin-%' AND source_code = '03-05')
        OR election_id LIKE 'sangiin-%'
      )
    GROUP BY election_id, election_kaiji, party
    ORDER BY election_kaiji, votes DESC NULLS LAST, party`);
  state.partiesByElection = {};
  for (const row of partyRows.toArray()) {
    const item = row.toJSON();
    const key = String(item.election_id || `shugiin-${item.election_kaiji}`);
    if (!state.partiesByElection[key]) state.partiesByElection[key] = [];
    state.partiesByElection[key].push(String(item.party));
    // 互換: 回次キーも残す（衆院）
    const kaiji = Number(item.election_kaiji);
    if (String(item.election_id || '').startsWith('shugiin-')) {
      if (!state.partiesByElection[kaiji]) state.partiesByElection[kaiji] = [];
      state.partiesByElection[kaiji].push(String(item.party));
    }
  }

  const smdPartyRows = await state.conn.query(`
    SELECT election_id, election_kaiji, party, max(value) AS votes
    FROM read_parquet('facts.parquet')
    WHERE metric = 'candidate_votes' AND contest IN ('smd', 'district')
      AND coalesce(party, '') NOT IN ('', '合計', '計')
    GROUP BY election_id, election_kaiji, party
    ORDER BY election_kaiji, votes DESC NULLS LAST, party`);
  state.partiesByElectionSmd = {};
  for (const row of smdPartyRows.toArray()) {
    const item = row.toJSON();
    const key = String(item.election_id || `shugiin-${item.election_kaiji}`);
    if (!state.partiesByElectionSmd[key]) state.partiesByElectionSmd[key] = [];
    state.partiesByElectionSmd[key].push(String(item.party));
    const kaiji = Number(item.election_kaiji);
    if (String(item.election_id || '').startsWith('shugiin-')) {
      if (!state.partiesByElectionSmd[kaiji]) state.partiesByElectionSmd[kaiji] = [];
      state.partiesByElectionSmd[kaiji].push(String(item.party));
    }
  }

  state.partiesByElectionYomi = {};
  if (state.hasYomiPrMeibo) {
    try {
      const yomiPartyRows = await state.conn.query(`
        SELECT election_kaiji, party,
               max(coalesce(party_seats, 0)) AS seats,
               count(*) AS n
        FROM read_parquet('yomi_pr_meibo.parquet')
        GROUP BY election_kaiji, party
        ORDER BY election_kaiji, seats DESC NULLS LAST, n DESC, party`);
      for (const row of yomiPartyRows.toArray()) {
        const item = row.toJSON();
        const key = `shugiin-${item.election_kaiji}`;
        if (!state.partiesByElectionYomi[key]) state.partiesByElectionYomi[key] = [];
        state.partiesByElectionYomi[key].push(String(item.party));
      }
      const yomiElections = await state.conn.query(`
        SELECT list_sort(list_distinct(list(election_kaiji))) AS elections
        FROM read_parquet('yomi_pr_meibo.parquet')`);
      const ye = Array.from(yomiElections.toArray()[0]?.toJSON()?.elections ?? [])
        .map(Number)
        .sort((a, b) => b - a);
      if (ye.length) state.electionsByChamber.shugiin.prlist = ye;
    } catch (yomiCoverageError) {
      console.warn('yomi pr meibo coverage skipped', yomiCoverageError);
      state.hasYomiPrMeibo = false;
    }
  }
}

async function init() {
  applyChamber('shugiin');
  applyTab('smd', { search: false });
  loadUpdatedAt();
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
      try {
        await state.db.registerFileBuffer(
          'municipality_facts.parquet',
          new Uint8Array(await muniResponse.arrayBuffer())
        );
      } catch (muniError) {
        console.warn('municipality parquet register skipped', muniError);
        state.hasMunicipality = false;
      }
    }

    const yomiResponse = await fetch(new URL('./data/yomi_pr_meibo.parquet', window.location.href).href);
    state.hasYomiPrMeibo = yomiResponse.ok;
    if (state.hasYomiPrMeibo) {
      try {
        await state.db.registerFileBuffer(
          'yomi_pr_meibo.parquet',
          new Uint8Array(await yomiResponse.arrayBuffer())
        );
      } catch (yomiError) {
        console.warn('yomi pr meibo register skipped', yomiError);
        state.hasYomiPrMeibo = false;
      }
    }

    const aliasResponse = await fetch(new URL('./data/person_name_aliases.parquet', window.location.href).href);
    state.hasPersonAliases = aliasResponse.ok;
    if (state.hasPersonAliases) {
      try {
        await state.db.registerFileBuffer(
          'person_name_aliases.parquet',
          new Uint8Array(await aliasResponse.arrayBuffer())
        );
      } catch (aliasError) {
        console.warn('person aliases register skipped', aliasError);
        state.hasPersonAliases = false;
      }
    }

    const seijiDistrictResponse = await fetch(new URL('./data/seiji_gakkai_smd_district_votes.parquet', window.location.href).href);
    state.hasSeijiSmdDistrict = seijiDistrictResponse.ok;
    if (state.hasSeijiSmdDistrict) {
      try {
        await state.db.registerFileBuffer(
          'seiji_gakkai_smd_district_votes.parquet',
          new Uint8Array(await seijiDistrictResponse.arrayBuffer())
        );
      } catch (seijiError) {
        console.warn('seiji district register skipped', seijiError);
        state.hasSeijiSmdDistrict = false;
      }
    }

    const seijiMuniResponse = await fetch(new URL('./data/seiji_gakkai_smd_municipality_votes.parquet', window.location.href).href);
    state.hasSeijiSmdMuni = seijiMuniResponse.ok;
    if (state.hasSeijiSmdMuni) {
      try {
        await state.db.registerFileBuffer(
          'seiji_gakkai_smd_municipality_votes.parquet',
          new Uint8Array(await seijiMuniResponse.arrayBuffer())
        );
      } catch (seijiMuniError) {
        console.warn('seiji muni register skipped', seijiMuniError);
        state.hasSeijiSmdMuni = false;
      }
    }

    const seijiTurnoutResponse = await fetch(new URL('./data/seiji_gakkai_turnout.parquet', window.location.href).href);
    state.hasSeijiTurnout = seijiTurnoutResponse.ok;
    if (state.hasSeijiTurnout) {
      try {
        await state.db.registerFileBuffer(
          'seiji_gakkai_turnout.parquet',
          new Uint8Array(await seijiTurnoutResponse.arrayBuffer())
        );
      } catch (seijiTurnoutError) {
        console.warn('seiji turnout register skipped', seijiTurnoutError);
        state.hasSeijiTurnout = false;
      }
    }

    const seijiPrResponse = await fetch(new URL('./data/seiji_gakkai_pr_votes.parquet', window.location.href).href);
    state.hasSeijiPr = seijiPrResponse.ok;
    if (state.hasSeijiPr) {
      try {
        await state.db.registerFileBuffer(
          'seiji_gakkai_pr_votes.parquet',
          new Uint8Array(await seijiPrResponse.arrayBuffer())
        );
      } catch (seijiPrError) {
        console.warn('seiji pr register skipped', seijiPrError);
        state.hasSeijiPr = false;
      }
    }

    const seijiPrMuniResponse = await fetch(new URL('./data/seiji_gakkai_pr_municipality_votes.parquet', window.location.href).href);
    state.hasSeijiPrMuni = seijiPrMuniResponse.ok;
    if (state.hasSeijiPrMuni) {
      try {
        await state.db.registerFileBuffer(
          'seiji_gakkai_pr_municipality_votes.parquet',
          new Uint8Array(await seijiPrMuniResponse.arrayBuffer())
        );
      } catch (seijiPrMuniError) {
        console.warn('seiji pr muni register skipped', seijiPrMuniError);
        state.hasSeijiPrMuni = false;
      }
    }

    const seijiNameMapResponse = await fetch(new URL('./data/seiji_candidate_name_map.parquet', window.location.href).href);
    state.hasSeijiNameMap = seijiNameMapResponse.ok;
    if (state.hasSeijiNameMap) {
      try {
        await state.db.registerFileBuffer(
          'seiji_candidate_name_map.parquet',
          new Uint8Array(await seijiNameMapResponse.arrayBuffer())
        );
      } catch (seijiNameMapError) {
        console.warn('seiji name map register skipped', seijiNameMapError);
        state.hasSeijiNameMap = false;
      }
    }

    const sangiinYomiNameResponse = await fetch(new URL('./data/sangiin_yomi_name_map.parquet', window.location.href).href);
    state.hasSangiinYomiNameMap = sangiinYomiNameResponse.ok;
    if (state.hasSangiinYomiNameMap) {
      try {
        await state.db.registerFileBuffer(
          'sangiin_yomi_name_map.parquet',
          new Uint8Array(await sangiinYomiNameResponse.arrayBuffer())
        );
      } catch (sangiinYomiNameError) {
        console.warn('sangiin yomi name map register skipped', sangiinYomiNameError);
        state.hasSangiinYomiNameMap = false;
      }
    }

    const partyAliasResponse = await fetch(new URL('./data/party_name_aliases.parquet', window.location.href).href);
    state.hasPartyAliases = partyAliasResponse.ok;
    if (state.hasPartyAliases) {
      try {
        await state.db.registerFileBuffer(
          'party_name_aliases.parquet',
          new Uint8Array(await partyAliasResponse.arrayBuffer())
        );
      } catch (partyAliasError) {
        console.warn('party aliases register skipped', partyAliasError);
        state.hasPartyAliases = false;
      }
    }

    state.conn = await state.db.connect();
    await loadCoverage();
    await loadSeijiCoverage();
    if (state.hasPartyAliases) {
      try {
        const aliasRows = await state.conn.query(`
          SELECT election_kaiji, alias_name, canonical_name
          FROM read_parquet('party_name_aliases.parquet')`);
        state.partyAliasGlobal = {};
        state.partyAliasByKaiji = {};
        for (const row of aliasRows.toArray()) {
          const item = row.toJSON();
          const alias = String(item.alias_name || '');
          const canon = String(item.canonical_name || '');
          if (!alias || !canon) continue;
          if (item.election_kaiji == null || item.election_kaiji === '') {
            state.partyAliasGlobal[alias] = canon;
          } else {
            state.partyAliasByKaiji[`${Number(item.election_kaiji)}|${alias}`] = canon;
          }
        }
      } catch (partyLoadError) {
        console.warn('party aliases load skipped', partyLoadError);
        state.hasPartyAliases = false;
      }
    }

    state.ready = true;
    setControlsEnabled(true);
    els.status.className = 'status ready';
    els.status.innerHTML = `<span class="pulse"></span>${displayNumber.format(state.factCount)}件を読み込み済み`;
    applyChamber('shugiin');
    applyTab('smd', { search: false });
  } catch (error) {
    console.error(error);
    const detail = String(error?.message || error).slice(0, 160);
    els.status.className = 'status error';
    els.status.innerHTML = `<span class="pulse"></span>読み込みに失敗しました${detail ? `（${detail}）` : ''}`;
    els.results.innerHTML = emptyRow(8, 'データを読み込めませんでした。通信環境を確認して再読み込みしてください。');
  }
}

$$('.chamber').forEach((button) => {
  button.addEventListener('click', () => {
    if (button.dataset.chamber === state.chamber) return;
    applyChamber(button.dataset.chamber);
  });
});
$$('.tab').forEach((button) => {
  button.addEventListener('click', () => {
    if (!state.ready || button.dataset.tab === state.tab) return;
    applyTab(button.dataset.tab, { search: false });
  });
});
if (els.dataSource) {
  els.dataSource.addEventListener('change', () => {
    if (canUseSeijiForTab()) {
      state.dataSourcePreference = els.dataSource.value || 'unified';
    }
    syncDataSourceUi();
    refreshElectionOptions();
    refreshPrefectureOptions();
    refreshDistrictOptions();
    refreshPartyOptions();
    refreshElectedFilterOptions();
    if (state.tab === 'muni') refreshMunicipalityOptions();
    if (state.tab === 'pr' && (usesSeijiSource() || usesUnifiedSource()) && els.geoLevel
      && els.geoLevel.value !== 'national' && els.geoLevel.value !== 'block') {
      els.geoLevel.value = 'block';
    }
    els.form.dataset.geolevel = els.geoLevel?.value || 'prefecture';
    if (usesSeijiSource()) {
      if (state.tab === 'smd' || state.tab === 'muni') {
        els.keywordLabel.textContent = '候補者名（かな可）';
        els.keyword.placeholder = '例：ヨコミチタカヒロ';
      }
      if (state.tab === 'smd') {
        els.tabNote.textContent = '政治学会SH-Dの小選挙区得票（1996-衆〜2017-衆・二次ソース）です。候補者名はかな表記です。総務省正本とは別系統で、当落・惜敗率はありません。';
      } else if (state.tab === 'muni') {
        els.tabNote.textContent = '政治学会SH-Dの市区町村別得票（1996-衆〜2017-衆・二次ソース）です。候補者名はかな表記です。総務省正本とは混ぜていません。';
      } else if (state.tab === 'turnout') {
        els.tabNote.textContent = '政治学会の投票・有権者（小選挙区=都道府県合算、比例=ブロック／全国）です。在外区分はありません。';
      } else if (state.tab === 'pr') {
        els.tabNote.textContent = '政治学会SH-Bの比例政党得票（1996-衆〜2017-衆）です。集計単位はブロック／全国のみ（都道府県粒なし）。';
        refreshPartyOptions();
      }
    } else if (state.tab === 'smd' || state.tab === 'muni' || state.tab === 'turnout' || state.tab === 'pr') {
      const tab = TABS[state.tab];
      els.tabNote.textContent = tab?.note || '';
      if (tab?.keywordLabel) {
        els.keywordLabel.textContent = tab.keywordLabel;
        els.keyword.placeholder = tab.keywordPlaceholder;
      }
    }
    els.head.innerHTML = currentHeaders().map((h) => (
      h === '得票' || h === '値' || h === '相対得票率' || h === '絶対得票率' || h === '惜敗率'
        || h === '名簿順位' || h === '当選枠'
        ? `<th class="numeric">${h}</th>`
        : `<th>${h}</th>`
    )).join('');
    clearResultsIdle();
  });
}
els.election.addEventListener('change', () => {
  if (state.tab === 'muni') refreshMunicipalityOptions();
  if (state.tab === 'pr' || state.tab === 'prlist' || state.tab === 'smd') refreshPartyOptions();
});
els.contest.addEventListener('change', () => {
  if (state.tab === 'turnout' && usesSeijiSource()) {
    refreshPrefectureOptions();
  }
});
els.prefecture.addEventListener('change', () => {
  if (state.tab === 'smd' || state.tab === 'muni') {
    refreshDistrictOptions();
    if (state.tab === 'muni') refreshMunicipalityOptions();
  }
  if (state.tab === 'pr' && els.geoLevel.value === 'list') {
    els.head.innerHTML = currentHeaders().map((h) => (
      h === '得票' || h === '値' || h === '相対得票率' || h === '絶対得票率' || h === '惜敗率'
        || h === '名簿順位' || h === '当選枠'
        ? `<th class="numeric">${h}</th>`
        : `<th>${h}</th>`
    )).join('');
  }
});
els.district.addEventListener('change', () => {
  if (state.tab === 'muni') refreshMunicipalityOptions();
});
els.geoLevel.addEventListener('change', () => {
  els.form.dataset.geolevel = els.geoLevel.value;
  if (state.tab === 'pr' && state.chamber === 'sangiin' && els.geoLevel.value === 'list') {
    els.keywordLabel.textContent = '候補者名';
    els.keyword.placeholder = '例：山田太郎';
  }
  els.head.innerHTML = currentHeaders().map((h) => (
    h === '得票' || h === '値' || h === '相対得票率' || h === '絶対得票率' || h === '惜敗率'
      || h === '名簿順位' || h === '当選枠'
      ? `<th class="numeric">${h}</th>`
      : `<th>${h}</th>`
  )).join('');
  if (state.ready && state.tab === 'pr') runSearch();
});
els.resultLimit?.addEventListener('change', () => {
  if (state.ready) { state.page = 1; runSearch(); }
});
els.gender?.addEventListener('change', () => {
  if (state.ready) { state.page = 1; runSearch(); }
});
els.prParty?.addEventListener('change', () => {
  if (state.ready && (state.tab === 'pr' || state.tab === 'prlist' || state.tab === 'smd')) runSearch();
});
els.electedFilter?.addEventListener('change', () => {
  if (state.ready && (state.tab === 'smd' || state.tab === 'prlist')) runSearch();
});
els.pagePrev?.addEventListener('click', () => {
  if (!state.ready || state.page <= 1) return;
  state.page -= 1;
  runSearch(null, { resetPage: false });
});
els.pageNext?.addEventListener('click', () => {
  if (!state.ready || state.page >= pageCount()) return;
  state.page += 1;
  runSearch(null, { resetPage: false });
});
els.form.addEventListener('submit', runSearch);
els.download?.addEventListener('click', downloadCsv);
init();
