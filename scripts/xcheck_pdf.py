"""독립 교차검증: 공식 PDF 표(pdfplumber 표 추출) ↔ 배포 JSON의 파싱된 날짜.
HWPX 추출 경로(build_data.py)나 validate.py와 코드를 공유하지 않는 별도 경로로 일정 날짜를 재확인한다.
사용: python3 -I scripts/xcheck_pdf.py source/2027_detail.pdf docs/data/2027/schedules.json
"""
import json, re, datetime, sys
import pdfplumber
rows = []
with pdfplumber.open(sys.argv[1]) as pdf:
    for pi, p in enumerate(pdf.pages, 1):
        for ti, t in enumerate(p.extract_tables()):
            for ri, r in enumerate(t):
                cells = [re.sub(r'\.\s+', '.', re.sub(r'\s+', ' ', (c or '')).strip()) for c in r]
                rows.append({'page': pi, 't': ti, 'r': ri, 'cells': cells, 'text': '|'.join(cells)})
S = json.load(open(sys.argv[2]))
WD = '월화수목금토일'
DRE = re.compile(r"(?<![\d.])(?:[’'](\d{2})\.)?(\d{1,2})[. ](\d{1,2})\.?(?:\(([월화수목금토일])\))?")
def pairs(text):
    out = []
    t = text.replace('∼', '~')
    for m in DRE.finditer(t):
        out.append((int(m.group(2)), int(m.group(3)), m.group(4), m.group(1)))
        tail = re.match(r"~(\d{1,2})(?![.\d])", t[m.end():])  # ’27.3.8~12 → 3.12
        if tail: out.append((int(m.group(2)), int(tail.group(1)), None, m.group(1)))
    return out
def iso2(d):
    y, m, dd = map(int, d.split('-')); return (m, dd)
def expected(s):
    seq = []
    for p in s['phases']:
        for r in p.get('registration_periods', []):
            seq += [iso2(r['start'])] + ([iso2(r['end'])] if r['end'] != r['start'] else [])
        for r in p.get('exam_periods', []):
            seq += [iso2(r['start'])] + ([iso2(r['end'])] if r['end'] != r['start'] else [])
        for r in p.get('result_dates', []):
            seq.append(iso2(r['date']))
        if p.get('document_submission'):
            ds = p['document_submission']; seq += [iso2(ds['start']), iso2(ds['end'])]
    return seq
def is_subseq(exp, got):
    it = iter(got); return all(any(e == g for g in it) for e in exp)
# KDATA 연도/요일 무표기 행, 다행 셀 대비: 연속 2행 결합 후보
cands = []
for i, r in enumerate(rows):
    txt = r['text']
    if i + 1 < len(rows) and rows[i+1]['page'] == r['page'] and rows[i+1]['t'] == r['t']:
        cands.append((r['page'], txt + '|' + rows[i+1]['text']))
    cands.append((r['page'], txt))
res = {'ok': [], 'ng': []}
wd_bad = set()
for c in cands:
    for m, d, w, yy in pairs(c[1]):
        if w:
            y = 2000 + int(yy) if yy else 2027
            try:
                if WD[datetime.date(y, m, d).weekday()] != w: wd_bad.add((c[0], m, d, w))
            except ValueError: wd_bad.add((c[0], m, d, 'invalid'))
for s in S:
    if not s['phases']: continue
    exp = expected(s)
    hit = [p for p, t in cands if is_subseq(exp, [(a, b) for a, b, _, _ in pairs(t)])]
    (res['ok'] if hit else res['ng']).append((s['schedule_id'], len(exp), sorted(set(hit))[:3]))
print('일정', len(res['ok']) + len(res['ng']), '건 중 PDF 표 행 일치', len(res['ok']))
for x in res['ng']: print('  미일치', x)
print('PDF 요일 표기 불일치', sorted(wd_bad) or '없음')
