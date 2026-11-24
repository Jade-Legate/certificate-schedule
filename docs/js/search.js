// 검색 정규화 및 순위
// 우선순위: 공식 종목명 완전 일치 > 앞부분 일치 > 부분 일치 > 별칭 일치(완전 > 앞부분 > 부분)

export const GRADE_FILTERS = [
  { code: '', label: '전체' },
  { code: 'craft', label: '기능사' },
  { code: 'industrial', label: '산업기사' },
  { code: 'engineer', label: '기사' },
  { code: 'master', label: '기능장' },
  { code: 'pe', label: '기술사' },
  { code: 'service', label: '서비스 분야' },
];

export function normalize(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFC')
    .replace(/[\s·‧･・\-_.,()（）[\]]/g, '');
}

export function buildIndex(qualifications) {
  return qualifications.map((q) => ({
    q,
    n: normalize(q.name),
    aliases: (q.aliases || []).map(normalize).filter(Boolean),
  }));
}

function rankOf(entry, term) {
  if (!term) return 10;
  if (entry.n === term) return 0;
  if (entry.n.startsWith(term)) return 1;
  if (entry.n.includes(term)) return 2;
  let best = 99;
  for (const a of entry.aliases) {
    if (a === term) best = Math.min(best, 3);
    else if (a.startsWith(term)) best = Math.min(best, 4);
    else if (a.includes(term)) best = Math.min(best, 5);
  }
  return best;
}

const GRADE_ORDER = { craft: 1, industrial: 2, engineer: 3, master: 4, pe: 5, service: 6 };
const STATUS_ORDER = { scheduled: 0, partially_held: 1, biennial_not_held: 2, not_conducted: 3, abolished: 4 };

export function search(index, rawTerm, grade) {
  const term = normalize(rawTerm);
  const out = [];
  for (const e of index) {
    if (grade && e.q.grade_code !== grade) continue;
    const r = rankOf(e, term);
    if (r >= 99) continue;
    out.push({ q: e.q, r });
  }
  out.sort((a, b) => a.r - b.r
    || (STATUS_ORDER[a.q.annual_status] ?? 9) - (STATUS_ORDER[b.q.annual_status] ?? 9)
    || (term ? a.q.name.length - b.q.name.length : 0)
    || (GRADE_ORDER[a.q.grade_code] || 9) - (GRADE_ORDER[b.q.grade_code] || 9)
    || a.q.name.localeCompare(b.q.name, 'ko'));
  return out.map((x) => x.q);
}

export function countByGrade(index, rawTerm) {
  const term = normalize(rawTerm);
  const c = { '': 0 };
  for (const e of index) {
    if (rankOf(e, term) >= 99) continue;
    c[''] += 1;
    c[e.q.grade_code] = (c[e.q.grade_code] || 0) + 1;
  }
  return c;
}
