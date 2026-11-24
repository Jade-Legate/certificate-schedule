// 시험일정 도메인 로직: KST 기준 날짜 계산, 접수 상태, 종목별 일정 뷰모델
// 공식 접수 시각이 날짜 데이터에 없으므로 시각을 만들어 내지 않는다(종일 일정·날짜 단위 비교).

const WD = ['일', '월', '화', '수', '목', '금', '토'];

export const EXAM_TYPE_LABEL = {
  regular: '정기검정',
  rolling: '상시검정',
  school_exempt: '필기시험 면제자 검정',
  training_exempt: '기술훈련과정 이수자 검정',
  occasional: '수시검정',
};

export const PHASE_LABEL = { written: '필기', practical: '실기', interview: '면접' };

export const STATUS_TEXT = {
  biennial_not_held: '2027년 미시행',
  partially_held: '정기검정 미시행',
  abolished: '폐지',
  not_conducted: '검정형 미실시',
};

/** KST 기준 오늘(YYYY-MM-DD). QA용 ?today=YYYY-MM-DD 로 대체 가능 */
export function todayKST(override) {
  if (override && /^\d{4}-\d{2}-\d{2}$/.test(override)) return override;
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' })
    .formatToParts(new Date());
  const g = (t) => parts.find((p) => p.type === t).value;
  return `${g('year')}-${g('month')}-${g('day')}`;
}

function toUTC(iso) { const [y, m, d] = iso.split('-').map(Number); return Date.UTC(y, m - 1, d); }
export function diffDays(a, b) { return Math.round((toUTC(b) - toUTC(a)) / 86400000); }

export function fmtDate(iso, { year = false } = {}) {
  const [y, m, d] = iso.split('-').map(Number);
  const w = WD[new Date(toUTC(iso)).getUTCDay()];
  return `${year ? `${y}. ` : ''}${m}. ${d}.(${w})`;
}

export function fmtPeriod(p, opts) {
  return p.start === p.end ? fmtDate(p.start, opts) : `${fmtDate(p.start, opts)} ~ ${fmtDate(p.end, opts)}`;
}

/** 접수 기간 상태 */
export function registrationStatus(periods, today, excluded = []) {
  if (!periods || !periods.length) return null;
  const start = periods[0].start; const end = periods[periods.length - 1].end;
  const inside = periods.find((p) => p.start <= today && today <= p.end);
  if (inside) {
    if (excluded.includes(today)) return { key: 'excluded', label: '오늘 접수 제외일', tone: 'warn' };
    const d = diffDays(today, inside.end);
    return { key: 'open', label: d === 0 ? '접수 중 · 오늘 마감' : `접수 중 · 마감 D-${d}`, tone: 'open' };
  }
  if (today < start) {
    const d = diffDays(today, start);
    return { key: 'upcoming', label: `접수 예정 · D-${d}`, tone: 'upcoming', days: d };
  }
  if (today > end) return { key: 'closed', label: '접수 마감', tone: 'closed' };
  // 복수 접수기간 사이
  const next = periods.find((p) => p.start > today);
  return { key: 'upcoming', label: `다음 접수 D-${diffDays(today, next.start)}`, tone: 'upcoming' };
}

function sortKey(s) {
  for (const p of s.phases) {
    const r = (p.registration_periods || [])[0] || (p.exam_periods || [])[0];
    if (r) return r.start;
  }
  return '9999';
}

/** 종목 하나의 일정 뷰모델 */
export function buildView(q, ctx) {
  const maps = ctx.mapsByQ.get(q.qualification_id) || [];
  const items = maps.map((m) => {
    const s = ctx.schedById.get(m.schedule_id);
    const ov = m.override || {};
    let phases = s.phases.filter((p) => !(ov.phases_excluded || []).includes(p.phase));
    phases = phases.map((p) => (p.phase === 'practical' && ov.practical_written_exam_date
      ? { ...p, specificNote: ov.note } : p));
    return { schedule: s, mapping: m, phases, noWritten: (ov.phases_excluded || []).includes('written') };
  });
  const order = { regular: 0, occasional: 1, school_exempt: 2, training_exempt: 3, rolling: 4 };
  items.sort((a, b) => (order[a.schedule.exam_type] - order[b.schedule.exam_type]) || sortKey(a.schedule).localeCompare(sortKey(b.schedule)));
  return { q, items };
}

/** 가장 가까운(진행 중 또는 다가오는) 원서접수 */
export function nextRegistration(view, today, { includeSpecial = false } = {}) {
  let best = null;
  for (const it of view.items) {
    const t = it.schedule.exam_type;
    if (t === 'rolling') continue;
    if (!includeSpecial && t !== 'regular') continue;
    for (const p of it.phases) {
      const regs = p.registration_periods || [];
      for (const r of regs) {
        if (r.end < today) continue;
        const cand = { item: it, phase: p, period: r, status: registrationStatus([r], today, p.excluded_dates) };
        if (!best || r.start < best.period.start || (r.start <= today && best.period.start > today)) best = cand;
      }
    }
  }
  return best;
}

export function roundTitle(it) {
  const s = it.schedule;
  if (s.exam_type === 'regular' || s.exam_type === 'occasional') return s.round;
  return EXAM_TYPE_LABEL[s.exam_type];
}

/** 단계별 표시 행 (라벨, 기간 목록, 상태) */
export function phaseRows(p, today, { isLastPhase } = {}) {
  const label = PHASE_LABEL[p.phase];
  const rows = [];
  if (p.registration_periods?.length) {
    rows.push({ kind: 'registration', label: `${label} 원서접수`, values: p.registration_periods.map((r) => (r.label ? `${r.label} ` : '') + fmtPeriod(r)),
      status: registrationStatus(p.registration_periods, today, p.excluded_dates || []),
      extra: (p.excluded_dates || []).map((d) => `${fmtDate(d)} 접수 제외`) });
  }
  if (p.document_submission) {
    rows.push({ kind: 'docs', label: '응시자격 서류제출', values: [fmtPeriod(p.document_submission)] });
  }
  if (p.exam_periods?.length) {
    rows.push({ kind: 'exam', label: `${label}시험`, values: p.exam_periods.map((r) => fmtPeriod(r)),
      extra: p.specificNote ? [p.specificNote] : [] });
  }
  if (p.result_dates?.length) {
    const resultLabel = isLastPhase ? (p.phase === 'written' ? '필기 합격자 발표' : '최종 합격자 발표') : `${label} 합격자 발표`;
    rows.push({ kind: 'result', label: resultLabel,
      values: p.result_dates.map((r) => `${r.label ? `${r.label} ` : ''}${fmtDate(r.date)}`),
      correction: p.correction || null });
  }
  return rows;
}
