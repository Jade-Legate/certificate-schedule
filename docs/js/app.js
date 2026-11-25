import { CONFIG } from './config.js';
import { initAnalytics, track, trackSearch } from './analytics.js';
import { GRADE_FILTERS, buildIndex, search, countByGrade } from './search.js';
import {
  EXAM_TYPE_LABEL, STATUS_TEXT, todayKST, buildView, nextRegistration, roundTitle, phaseRows,
  fmtDate, fmtPeriod,
} from './schedule.js';

const $ = (s, el = document) => el.querySelector(s);
const params = new URLSearchParams(location.search);
// QA용 날짜 고정(?today=YYYY-MM-DD)은 로컬 개발 환경에서만 허용한다. 운영 주소에서는 무시.
const IS_LOCAL = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
const TODAY = todayKST(IS_LOCAL ? params.get('today') : null);
const mq = matchMedia('(max-width: 899px)');

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const state = { year: CONFIG.defaultYear, q: '', grade: '', selected: null, data: null };
let ctx = null; let index = null;

// ------------------------------------------------------------------ 데이터 로딩
async function loadJSON(path) {
  const r = await fetch(path, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

async function loadData(year) {
  const base = `data/${year}/`;
  const [qualifications, schedules, mappings, agencies, changes] = await Promise.all(
    ['qualifications', 'schedules', 'mappings', 'agencies', 'changes'].map((n) => loadJSON(`${base}${n}.json`)));
  const schedById = new Map(schedules.map((s) => [s.schedule_id, s]));
  const mapsByQ = new Map();
  for (const m of mappings) {
    if (!schedById.has(m.schedule_id)) continue;
    if (!mapsByQ.has(m.qualification_id)) mapsByQ.set(m.qualification_id, []);
    mapsByQ.get(m.qualification_id).push(m);
  }
  const changesByQ = new Map();
  for (const c of changes) {
    if (!changesByQ.has(c.qualification_id)) changesByQ.set(c.qualification_id, []);
    changesByQ.get(c.qualification_id).push(c);
  }
  return {
    qualifications, qById: new Map(qualifications.map((q) => [q.qualification_id, q])),
    schedById, mapsByQ, changesByQ, agencies: new Map(agencies.map((a) => [a.agency_id, a])), agencyList: agencies,
  };
}

// ------------------------------------------------------------------ URL 상태
function readURL() {
  const p = new URLSearchParams(location.search);
  state.q = p.get('q') || '';
  const g = p.get('grade') || '';
  state.grade = GRADE_FILTERS.some((x) => x.code === g) ? g : '';
  state.selected = p.get('qualification') || null;
  const y = Number(p.get('year'));
  if (y) state.year = y;
}

function writeURL(push) {
  const p = new URLSearchParams();
  p.set('year', state.year);
  if (state.q) p.set('q', state.q);
  if (state.grade) p.set('grade', state.grade);
  if (state.selected) p.set('qualification', state.selected);
  // 블로그 유입 UTM 등 기타 파라미터 보존
  for (const [k, v] of new URLSearchParams(location.search)) if (/^utm_/.test(k) || (IS_LOCAL && k === 'today')) p.set(k, v);
  const url = `${location.pathname}?${p.toString()}`;
  if (url === `${location.pathname}${location.search}`) return;
  history[push ? 'pushState' : 'replaceState']({ ...state, data: null }, '', url);
}

// ------------------------------------------------------------------ 목록
function badgeFor(q) {
  if (q.annual_status !== 'scheduled') {
    const tone = q.annual_status === 'partially_held' ? 'warn' : 'muted';
    return h('span', { class: `chip chip--${tone}` }, STATUS_TEXT[q.annual_status]);
  }
  const view = buildView(q, ctx);
  if (view.items.every((i) => i.schedule.exam_type === 'rolling')) return h('span', { class: 'chip chip--info' }, '상시검정');
  const nx = nextRegistration(view, TODAY);
  if (!nx) return h('span', { class: 'chip chip--muted' }, '2027 접수 종료');
  if (nx.status.key === 'open') return h('span', { class: 'chip chip--open' }, '접수 중');
  const md = fmtDate(nx.period.start).replace(/\s/g, '').replace(/\.\(.\)$/, '').replace(/\.$/, '');
  return h('span', { class: 'chip chip--upcoming', title: `다음 원서접수 시작 ${fmtDate(nx.period.start)}` }, `${md} 접수 시작`);
}

function renderGrades(counts) {
  const box = $('#grades');
  box.replaceChildren(...GRADE_FILTERS.map((g) => {
    const on = state.grade === g.code;
    return h('button', {
      type: 'button', role: 'radio', 'aria-checked': String(on), class: `tab${on ? ' is-on' : ''}`, 'data-grade': g.code,
      tabindex: on ? '0' : '-1',
      onclick: () => setGrade(g.code),
      onkeydown: (e) => {
        const btns = [...box.querySelectorAll('button')]; const i = btns.indexOf(e.currentTarget);
        let j = null;
        if (e.key === 'ArrowRight') j = (i + 1) % btns.length;
        if (e.key === 'ArrowLeft') j = (i - 1 + btns.length) % btns.length;
        if (j != null) { e.preventDefault(); setGrade(btns[j].dataset.grade); box.querySelector(`[data-grade="${btns[j].dataset.grade}"]`).focus(); }
      },
    }, g.label, h('span', { class: 'tab__count' }, String(counts[g.code] || 0)));
  }));
}

function renderList() {
  const counts = countByGrade(index, state.q);
  renderGrades(counts);
  const list = search(index, state.q, state.grade);
  const gl = GRADE_FILTERS.find((g) => g.code === state.grade)?.label;
  $('#count').textContent = state.q || state.grade
    ? `검색 결과 ${list.length.toLocaleString()}건`
    : `전체 ${list.length.toLocaleString()}종목`;
  if (state.grade && gl !== '전체') $('#count').append(h('span', { class: 'results__filter' }, ` · ${gl}`));
  const ul = $('#results');
  const frag = document.createDocumentFragment();
  for (const q of list) {
    const ag = ctx.agencies.get(q.agency_id);
    const on = q.qualification_id === state.selected;
    frag.append(h('li', {},
      h('a', {
        class: `item${on ? ' is-on' : ''}`, href: `?year=${state.year}&qualification=${q.qualification_id}`,
        'aria-current': on ? 'true' : null, 'data-id': q.qualification_id,
        onclick: (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); select(q.qualification_id, { push: true, from: 'list' }); },
      },
      h('span', { class: 'item__main' },
        h('span', { class: 'item__name' }, q.name),
        h('span', { class: 'item__meta' }, `${q.grade === '서비스' ? '서비스 분야' : q.grade} · ${ag.name}`)),
      badgeFor(q))));
  }
  ul.replaceChildren(frag);
  const empty = $('#empty');
  if (!list.length) {
    empty.hidden = false;
    empty.replaceChildren(
      h('p', { class: 'empty__title' }, `‘${state.q}’에 대한 검색 결과가 없어요.`),
      h('p', {}, '띄어쓰기 없이 입력하거나 종목명 일부(예: 전기, 지게차)로 검색해 보세요. 등급 필터가 켜져 있다면 ‘전체’로 바꿔 보세요.'),
      state.grade ? h('button', { type: 'button', class: 'btn btn--ghost', onclick: () => setGrade('') }, '전체 등급에서 찾기') : null,
    );
  } else empty.hidden = true;
  trackSearch({ term: state.q.trim(), grade: state.grade, count: list.length });
  $('#clear').hidden = !state.q;
  return list;
}

// ------------------------------------------------------------------ 상세
const ELIGIBILITY = {
  pe: '기술사 등급은 응시자격(학력·경력 등)을 갖춰야 응시할 수 있어요.',
  master: '기능장 등급은 응시자격(경력 등)을 갖춰야 응시할 수 있어요.',
  engineer: '기사 등급은 응시자격(학력·경력 등)을 갖춰야 응시할 수 있어요. 필기 합격 후 지정 기간 내 응시자격 서류를 제출해야 합격 처리됩니다.',
  industrial: '산업기사 등급은 응시자격(학력·경력 등)을 갖춰야 응시할 수 있어요. 필기 합격 후 지정 기간 내 응시자격 서류를 제출해야 합격 처리됩니다.',
  service: null,
  craft: '기능사 등급은 응시자격 제한이 없어요.',
};
const SPECIAL_NOTICE = {
  school_exempt: '산업수요 맞춤형 고등학교(마이스터고)·특성화고 등에서 필기시험 면제 확인을 받은 학생만 응시하는 별도 검정이에요. 모든 특성화고·마이스터고 학생이 자동으로 응시할 수 있는 것은 아니며, 면제 여부는 학교(시·도교육감)에서 확인합니다. 일반 필기시험 면제자는 응시할 수 없어요.',
  training_exempt: '기술훈련과정을 70/100 이상 이수한 사람만 응시할 수 있는 별도 검정이에요. 일반 필기시험 면제자는 응시할 수 없어요.',
  occasional: '수시검정은 해외취업·선박 승선 등 특수한 목적의 대상자를 위해 별도로 시행돼요. 일반 응시 가능 여부는 시행기관에 확인하세요.',
};

function statusBanner(q) {
  const msg = {
    biennial_not_held: '해당 종목은 격년제 시행에 따라 2027년 시험이 시행되지 않습니다.',
    partially_held: '해당 종목은 격년제 시행에 따라 2027년 정기검정(필기·실기)이 시행되지 않습니다. 단, 산업수요 맞춤형 고등학교·특성화고 등 필기시험 면제자 검정은 정상 시행됩니다.',
    abolished: '해당 종목은 폐지되어 2027년 시험이 시행되지 않습니다.',
    not_conducted: '해당 종목은 시행기관(한국산업안전보건공단)의 내부 사정으로 2027년 검정형 시험이 시행되지 않습니다.',
  }[q.annual_status];
  if (!msg) return null;
  const extra = (ctx.changesByQ.get(q.qualification_id) || []).map((c) => c.reason);
  return h('div', { class: `notice notice--${q.annual_status === 'partially_held' ? 'warn' : 'muted'}`, role: 'note' },
    h('p', { class: 'notice__title' }, msg),
    extra.length ? h('ul', { class: 'notice__list' }, extra.map((t) => h('li', {}, t))) : null);
}

const PHASE_NAME = { written: '필기', practical: '실기', interview: '면접' };
function rowLabel(label, phase) {
  // 단계 묶음 제목이 있으므로 행 이름에서 단계명을 뺀다 ('필기 원서접수' → '원서접수', '필기시험' → '시험일')
  const name = PHASE_NAME[phase];
  if (label === `${name}시험`) return '시험일';
  return label.startsWith(`${name} `) ? label.slice(name.length + 1) : label;
}

function renderPhaseTable(it, wrap) {
  it.phases.forEach((p, i) => {
    const group = h('section', { class: 'phase', 'aria-label': `${PHASE_NAME[p.phase]} 일정` },
      h('h4', { class: 'phase__title' }, PHASE_NAME[p.phase]));
    const dl = h('dl', { class: 'timeline' });
    for (const r of phaseRows(p, TODAY, { isLastPhase: i === it.phases.length - 1 })) {
      dl.append(h('div', { class: `timeline__row timeline__row--${r.kind}` },
        h('dt', {}, rowLabel(r.label, p.phase)),
        h('dd', {},
          h('span', { class: 'timeline__values' }, r.values.map((v) => h('span', { class: 'timeline__value' }, v))),
          r.status ? h('span', { class: `chip chip--${r.status.tone}` }, r.status.label) : null,
          (r.extra || []).map((x) => h('span', { class: 'timeline__extra' }, x)),
          r.correction ? h('span', { class: 'timeline__extra timeline__extra--fix' },
            `공식 자료에는 ‘${r.correction.original}’로 적혀 있지만 시험일보다 앞선 날짜라 2027년 오기로 보고 표시했어요. 시행기관의 정정 공고로 확인된 내용은 아니니 접수 전 시행기관 누리집에서 확인하세요.`) : null)));
    }
    group.append(dl);
    wrap.append(group);
  });
  if (it.noWritten) wrap.append(h('p', { class: 'muted small' }, '이 종목은 필기시험 없이 실기시험만 시행해요.'));
  const notes = [...new Set([...it.phases.flatMap((p) => p.notes || []), ...(it.schedule.notes || [])])];
  if (it.mapping.eligibility_note) notes.unshift(it.mapping.eligibility_note);
  if (notes.length) {
    wrap.append(h('details', { class: 'notes' }, h('summary', {}, `유의사항 ${notes.length}건`),
      h('ul', {}, notes.map((n) => h('li', {}, n)))));
  }
}

function renderDetail({ focus = false } = {}) {
  const box = $('#detail');
  const q = state.selected && ctx.qById.get(state.selected);
  document.body.classList.toggle('has-selection', !!q);
  if (!q) {
    box.replaceChildren(h('div', { class: 'detail__placeholder' },
      h('p', { class: 'detail__placeholder-title' }, state.selected ? '해당 자격증을 찾을 수 없어요' : '자격증을 선택하세요'),
      h('p', {}, state.selected ? '링크가 잘못되었거나 2027년 데이터에 없는 종목이에요. 이름으로 다시 검색해 주세요.' : '검색 결과에서 종목을 고르면 2027년 회차별 일정을 보여 드려요.')));
    document.title = '2027 국가기술자격 시험일정 | 데뷔';
    return;
  }
  const ag = ctx.agencies.get(q.agency_id);
  const view = buildView(q, ctx);
  const types = [...new Set(view.items.map((i) => i.schedule.exam_type))];
  document.title = `${q.name} 2027 시험일정 | 데뷔`;

  const back = h('button', { type: 'button', class: 'back', onclick: () => {
    if (history.state && history.state.fromList) history.back(); else select(null, { push: true });
  } }, h('span', { 'aria-hidden': 'true' }, '←'), ' 검색 결과');

  const head = h('div', { class: 'detail__head' },
    h('div', { class: 'detail__badges' },
      h('span', { class: 'badge' }, q.grade === '서비스' ? '서비스 분야' : q.grade),
      types.map((t) => h('span', { class: `badge badge--${t === 'regular' ? 'line' : 'soft'}` }, EXAM_TYPE_LABEL[t]))),
    h('h2', { class: 'detail__title', id: 'detail-title', tabindex: '-1' }, q.name),
    h('p', { class: 'detail__agency' }, `시행기관 · ${ag.name}`));

  const parts = [back, head];
  const banner = statusBanner(q); if (banner) parts.push(banner);
  if (q.data_notice) parts.push(h('div', { class: 'notice notice--warn', role: 'note' }, h('p', { class: 'notice__title' }, '확인이 필요한 일정이 있어요'), h('p', {}, q.data_notice)));

  // 가장 가까운 접수
  const nx = nextRegistration(view, TODAY, { includeSpecial: !view.items.some((i) => i.schedule.exam_type === 'regular') });
  if (nx) {
    parts.push(h('div', { class: `next next--${nx.status.tone}` },
      h('p', { class: 'next__label' }, nx.status.key === 'open' ? '지금 접수 중' : '가장 가까운 원서접수'),
      h('p', { class: 'next__title' }, `${roundTitle(nx.item)} ${({ written: '필기', practical: '실기', interview: '면접' })[nx.phase.phase]} 원서접수`),
      h('p', { class: 'next__date' }, fmtPeriod(nx.period, { year: true })),
      h('span', { class: `chip chip--${nx.status.tone}` }, nx.status.label)));
  }

  const regularish = view.items.filter((i) => i.schedule.exam_type !== 'rolling');
  const rolling = view.items.find((i) => i.schedule.exam_type === 'rolling');
  if (rolling) {
    parts.push(h('div', { class: 'notice notice--info', role: 'note' },
      h('p', { class: 'notice__title' }, '상시검정 종목으로, 세부 시험일정은 시행기관의 별도 공고를 확인해 주세요.'),
      rolling.mapping.eligibility_note ? h('p', {}, rolling.mapping.eligibility_note) : null,
      h('ul', { class: 'notice__list' }, rolling.schedule.notes.map((n) => h('li', {}, n)))));
  }

  if (regularish.length) {
    const tabsId = `rounds-${q.qualification_id}`;
    const defaultIdx = Math.max(0, nx ? regularish.indexOf(nx.item) : 0);
    const tablist = h('div', { class: 'rounds', role: 'tablist', 'aria-label': '시행 회차', id: tabsId });
    const panels = h('div', { class: 'round-panels' });
    regularish.forEach((it, i) => {
      const on = i === defaultIdx; const tid = `${tabsId}-t${i}`; const pid = `${tabsId}-p${i}`;
      const special = it.schedule.exam_type !== 'regular';
      tablist.append(h('button', { type: 'button', role: 'tab', id: tid, 'aria-controls': pid, 'aria-selected': String(on), tabindex: on ? '0' : '-1',
        class: `round${special ? ' round--special' : ''}`,
        onclick: (e) => activateTab(tablist, e.currentTarget),
        onkeydown: (e) => {
          const tabs = [...tablist.querySelectorAll('[role=tab]')]; const k = tabs.indexOf(e.currentTarget); let j = null;
          if (e.key === 'ArrowRight') j = (k + 1) % tabs.length; if (e.key === 'ArrowLeft') j = (k - 1 + tabs.length) % tabs.length;
          if (e.key === 'Home') j = 0; if (e.key === 'End') j = tabs.length - 1;
          if (j != null) { e.preventDefault(); activateTab(tablist, tabs[j]); tabs[j].focus(); }
        } }, roundTitle(it)));
      const panel = h('div', { role: 'tabpanel', id: pid, 'aria-labelledby': tid, class: 'round-panel', hidden: !on, tabindex: '0' });
      if (special) panel.append(h('div', { class: 'notice notice--warn notice--compact', role: 'note' }, h('p', {}, SPECIAL_NOTICE[it.schedule.exam_type])));
      if (it.schedule.exam_type === 'regular' && /분야|기능사|기사/.test(it.schedule.schedule_group) && it.schedule.agency_id === 'KCA') {
        panel.append(h('p', { class: 'muted small' }, `적용 구분: ${it.schedule.schedule_group.replace('KCA-', '')}`));
      }
      renderPhaseTable(it, panel);
      panels.append(panel);
    });
    parts.push(h('div', { class: 'section' }, h('h3', { class: 'section__title' }, '2027년 시행 회차'), tablist, panels));
  }

  if (ELIGIBILITY[q.grade_code] && q.annual_status !== 'abolished' && q.annual_status !== 'not_conducted') {
    parts.push(h('p', { class: 'eligibility' }, h('strong', {}, '응시자격 '), ELIGIBILITY[q.grade_code]));
  }
  const otherChanges = q.annual_status === 'scheduled' ? (ctx.changesByQ.get(q.qualification_id) || []) : [];
  if (otherChanges.length) parts.push(h('div', { class: 'notice notice--info', role: 'note' }, h('p', { class: 'notice__title' }, '변경사항'), h('ul', { class: 'notice__list' }, otherChanges.map((c) => h('li', {}, c.reason)))));

  // 액션
  const url = ag.registration_url || ag.official_url;
  const actions = h('div', { class: 'actions' },
    h('a', { class: 'btn btn--primary btn--lg', href: url, target: '_blank', rel: 'noopener',
      onclick: () => track('official_site_click', { qualification_id: q.qualification_id, agency_id: q.agency_id }) },
    `${ag.site_name} 바로가기`, h('span', { class: 'sr-only' }, ' (새 창)')),
    h('p', { class: 'caution' }, `공고된 계획을 정리한 참고용 일정이에요. 원서접수 전 ${ag.site_name}에서 최종 일정을 꼭 확인하세요.`));
  parts.push(actions);
  parts.push(h('p', { class: 'source' }, `출처: 고용노동부 공고 제2026-518호 2027년 국가기술자격 검정시행계획 · ${q.source_reference}`));

  box.replaceChildren(...parts);
  track('schedule_view', { qualification_id: q.qualification_id, grade: q.grade_code, annual_status: q.annual_status });
  if (focus) {
    if (mq.matches) window.scrollTo({ top: 0 });
    $('#detail-title').focus({ preventScroll: !mq.matches });
  }
}

function activateTab(tablist, btn) {
  for (const t of tablist.querySelectorAll('[role=tab]')) {
    const on = t === btn; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
    document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
  }
}

// ------------------------------------------------------------------ 상호작용
function select(id, { push = false, from = null } = {}) {
  state.selected = id;
  if (id) track('certificate_select', { qualification_id: id, source: from || 'url' });
  if (push) {
    writeURL(true);
    if (from === 'list') history.replaceState({ ...history.state, fromList: true }, '', location.href);
  }
  for (const a of document.querySelectorAll('.item')) {
    const on = a.dataset.id === id; a.classList.toggle('is-on', on);
    if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
  }
  renderDetail({ focus: !!id && from === 'list' });
}

function setGrade(code) { state.grade = code; renderList(); writeURL(false); }
let typingTimer = null;
function onInput() {
  state.q = $('#q').value;
  renderList();
  clearTimeout(typingTimer); typingTimer = setTimeout(() => writeURL(false), 300);
}

function fmtDot(iso) { const [y, m, d] = iso.split('-').map(Number); return `${y}.${String(m).padStart(2, '0')}.${String(d).padStart(2, '0')}.`; }

function renderSource(meta) {
  const ds = meta.datasets[String(state.year)];
  const ext0 = (href, text) => h('a', { href, target: '_blank', rel: 'noopener' }, text, h('span', { class: 'sr-only' }, ' (새 창)'));
  // 데이터 갱신일은 metadata.json 의 data_updated(시험일정 데이터 기준)만 쓴다. 배포일과 무관.
  $('#data-meta').replaceChildren(
    h('span', {}, `데이터 최종 업데이트: ${fmtDot(ds.data_updated)}`),
    h('span', { class: 'search-info__sep', 'aria-hidden': 'true' }, '·'),
    h('span', {}, '출처: ', ext0(CONFIG.sourceNoticeUrl, ds.announcement_no)));
  const ext = (href, text) => h('a', { href, target: '_blank', rel: 'noopener' }, text, h('span', { class: 'sr-only' }, ' (새 창)'));
  const items = [
    ['출처 문서', h('span', {}, ext(CONFIG.sourceNoticeUrl, `${ds.title} (고용노동부 공지사항)`))],
    ['공고번호', ds.announcement_no],
    ['공고일', `${fmtDate(ds.published, { year: true })} (문서 기재) · 고용노동부 누리집 게시 ${fmtDate(ds.posted, { year: true })}`],
    ['데이터 최종 업데이트', fmtDate(ds.data_updated, { year: true })],
    ['수록 범위', `${ds.counts.qualifications}종목 = 공식 집계 ${ds.counts.official_total}종목 + 폐지 2종목 + 검정형 미실시 1종목. ${ds.scope_note}`],
    ['저작권', h('span', {}, '원문 저작권은 고용노동부 및 관계기관에 있습니다. ', ext(CONFIG.sourceCopyrightUrl, '고용노동부 저작권 정책'))],
  ];
  const meta1 = () => h('dl', { class: 'meta' }, items.map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', {}, v instanceof Node ? v.cloneNode(true) : v))));
  const links = h('ul', { class: 'agency-links' }, ctx.agencyList.map((a) => h('li', {}, ext(a.official_url, a.name))));
  $('#source-info').replaceChildren(h('div', {}, h('h2', { class: 'footer__title' }, '데이터 출처'), meta1()));
  $('#source-body').replaceChildren(meta1(),
    h('p', { class: 'small' }, '데뷔(DEBUT)가 운영하는 비공식 참고 서비스입니다. 공고된 검정시행계획 상세본(HWPX)에서 일정을 옮기고 공식 PDF와 자동 대조 검사를 거쳤지만, 이는 데이터 옮김 과정의 점검일 뿐 시행기관의 확정 일정을 보증하지 않습니다. 원서접수 전 반드시 시행기관의 공식 공고를 확인하세요.'),
    h('h3', { class: 'section__title' }, '시행기관 바로가기'), links);
  if (CONFIG.contact) {
    const c = CONFIG.contact; const href = /^https?:/.test(c) ? c : `mailto:${c}`;
    $('#operator').replaceChildren('운영 데뷔(DEBUT) · 오류 신고·문의 ', h('a', { href }, c));
  }
}

function showError(err) {
  console.warn('[certificate-schedule] 데이터 로딩 실패', err);
  $('#count').textContent = '데이터를 불러오지 못했어요';
  $('#results').replaceChildren();
  const empty = $('#empty'); empty.hidden = false;
  empty.replaceChildren(h('p', { class: 'empty__title' }, '시험일정 데이터를 불러오지 못했어요.'),
    h('p', {}, '네트워크 상태를 확인한 뒤 다시 시도해 주세요. 문제가 계속되면 큐넷(www.q-net.or.kr) 등 시행기관 누리집에서 일정을 확인할 수 있어요.'),
    h('button', { type: 'button', class: 'btn btn--primary', onclick: () => location.reload() }, '다시 시도'));
}

async function init() {
  initAnalytics();
  readURL();
  $('#q').value = state.q;
  if (CONFIG.roadmapUrl) {
    const a = $('#cta'); a.hidden = false; a.href = CONFIG.roadmapUrl;
    a.addEventListener('click', () => track('roadmap_cta_click', { qualification_id: state.selected || '' }));
  }
  let meta;
  try {
    meta = await loadJSON('data/metadata.json');
    if (!meta.datasets[String(state.year)]) state.year = meta.current_year;
    ctx = await loadData(state.year);
  } catch (e) { showError(e); return; }
  index = buildIndex(ctx.qualifications);
  renderSource(meta);
  renderList();
  renderDetail();
  writeURL(false);
  $('#q').addEventListener('input', onInput);
  $('#search-form').addEventListener('submit', (e) => {
    e.preventDefault(); writeURL(true);
    const first = $('#results .item'); if (first && mq.matches) first.scrollIntoView({ block: 'nearest' });
    $('#q').blur();
  });
  $('#clear').addEventListener('click', () => { $('#q').value = ''; onInput(); writeURL(true); $('#q').focus(); });
  window.addEventListener('popstate', () => {
    readURL(); $('#q').value = state.q; renderList(); renderDetail();
  });
  const dlg = $('#source-dialog');
  $('#open-source').addEventListener('click', () => dlg.showModal());
  $('#close-source').addEventListener('click', () => dlg.close());
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
}

init();
