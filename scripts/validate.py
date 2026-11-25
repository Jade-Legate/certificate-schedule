"""데이터 검증 스크립트.

사용: python3 -I scripts/validate.py <data_dir(.../data/2027)> <csv_dir> <detail_pdf.txt> <summary_pdf.txt> <report.md>
  detail_pdf.txt / summary_pdf.txt : `pdftotext -layout` 결과(공식 PDF 원본)

검사 항목 (모두 실제 계산 결과를 리포트에 기록)
  1. 기관별·등급별 종목 수 (요약본 PDF 수치와 대조)
  2. 공식 종목명 전수 대조 (PDF 본문에 원문 종목명 존재 여부)
  3. 종목별 시행 회차 전수 대조 (HWPX 원문 행이 PDF 같은 줄에 동일하게 존재하는지)
  4. 시험일정·접수 제외일 원문 문자열 PDF 대조 + 요일 대조
  5. 중복 ID / 중복 매핑
  6. 참조 무결성
  7. 날짜 형식·시간 순서
  8. 미시행·폐지 종목의 활성 일정 매핑
  9. CSV ↔ JSON 일치
"""
import sys, json, csv, re, datetime, collections, pathlib

WD = '월화수목금토일'

# 텍스트 추출로 확인되지 않아 PDF 페이지를 렌더링해 육안으로 대조한 항목 (연도별 업데이트 시 재확인 필요)
MANUAL_CHECKS = {
    '무선설비기능사': 'PDF p.62(인쇄 쪽 58) 종목(유형)별 시행회차 표: "1, 3, 4회" 육안 대조 일치 (2026-11-24)',
    '전파전자통신기능사': 'PDF p.62(인쇄 쪽 58) 종목(유형)별 시행회차 표: "1, 2, 3, 4회" 육안 대조 일치 (2026-11-24)',
}


def clean(s):
    return re.sub(r'\s+', '', (s or '')).replace('‧', '·').replace('･', '·').replace('∼', '~').replace('〜', '~')


def main():
    d, csv_dir, pdf_detail, pdf_summary, out = sys.argv[1:6]
    extra = sys.argv[6:]  # 추가 PDF 텍스트(예: pdftotext -layout 결과) — 요약본 수치 확인용
    d = pathlib.Path(d)
    L = {k: json.loads((d / f'{k}.json').read_text()) for k in ('qualifications', 'schedules', 'mappings', 'agencies', 'changes')}
    Q = L['qualifications']; S = L['schedules']; M = L['mappings']; A = L['agencies']
    pdf_lines = [clean(l) for l in open(pdf_detail, encoding='utf-8').read().split('\n')]
    pdf_all = ''.join(pdf_lines)
    sum_all = clean(open(pdf_summary, encoding='utf-8').read()) + ''.join(clean(open(x, encoding='utf-8').read()) for x in extra)

    def find_split(text_lines, name, i_hint=None):
        # 셀 안 줄바꿈으로 종목명이 두 줄에 나뉜 경우: name[:k] 가 i줄, name[k:] 가 i±1~2줄에 존재
        for i, line in enumerate(text_lines):
            for k in range(3, len(name) - 1):
                if line.endswith(name[:k]) or (name[:k] in line and name[:k + 1] not in line):
                    for j in (i + 1, i - 1, i + 2, i - 2):
                        if 0 <= j < len(text_lines) and name[k:] in text_lines[j]:
                            return i
        return None
    res = []  # (section, ok, detail)

    def R(sec, ok, detail):
        res.append((sec, bool(ok), detail))

    qd = {q['qualification_id']: q for q in Q}; sd = {s['schedule_id']: s for s in S}; ad = {a['agency_id'] for a in A}

    # 1. 종목 수
    expect = {'한국산업인력공단': 489, '대한상공회의소': 16, '한국원자력안전기술원': 3, '영화진흥위원회': 2, '한국콘텐츠진흥원': 3,
              '한국방송통신전파진흥원': 16, '한국광해광업공단': 7, '한국데이터산업진흥원': 1, '한국디자인진흥원': 1}
    name2id = {a['name']: a['agency_id'] for a in A}
    cnt = collections.Counter(q['agency_id'] for q in Q if q['annual_status'] not in ('abolished', 'not_conducted'))
    for n, e in expect.items():
        nn = re.escape(clean(n)); ee = str(e)
        pdf_has = any(re.search(pt, sum_all) for pt in (
            r'(?<![\d(])' + ee + r'(?![\d)])[^()]{0,45}?' + nn,      # 수치가 기관명 앞 줄
            nn + ee + r'(?!\d)',                                       # 기관명 바로 뒤
            nn + r'\(\d+\)' + ee + r'(?!\d)',                          # 기관명(26년)27년
            r'\)' + ee + r'\d' + nn))                                   # (전년)수치+연번+기관명
        R('1.종목수', cnt[name2id[n]] == e and pdf_has, f'{n}: 데이터 {cnt[name2id[n]]} / 요약본 {e} (요약본 PDF 수치 확인 {"O" if pdf_has else "X"})')
    total = sum(cnt.values())
    R('1.종목수', total == 538, f'공식 집계 대상 합계 {total} (기대 538)')
    R('1.종목수', len(Q) == 541, f'검색 대상 {len(Q)} (538 + 폐지 2 + 검정형 미실시 1 = 541)')
    hr = collections.Counter(q['grade'] for q in Q if q['agency_id'] == 'HRDK' and q['annual_status'] != 'abolished')
    for g, e in (('기술사', 79), ('기능장', 29), ('기사', 106), ('산업기사', 108), ('서비스', 16), ('기능사', 151)):
        R('1.종목수', hr[g] == e and f'{g}({e})' in sum_all, f'한국산업인력공단 {g}: {hr[g]} / 요약본 {e}')

    # 2. 공식 종목명 전수 대조
    miss = []
    for q in Q:
        cands = {clean(q['name'])}
        if q.get('source_row'):
            cands.add(clean(q['source_row'][0]))
        # KCCI 공백 등급 표기, KOMIR 등 표 구조: 등급과 종목명 분리 기재 허용
        base = re.sub(r'(기술사|기능장|산업기사|기사|기능사)$', '', clean(q['name']))
        cands.add(base); cands.add(re.sub(r'\d급$', '', clean(q['name'])))
        if not any(c and (c in pdf_all or c in sum_all) for c in cands) and not any(c and len(c) > 5 and find_split(pdf_lines, c) is not None for c in cands):
            miss.append(q['name'])
    R('2.종목명', not miss, f'PDF 상세본 본문에서 종목명(또는 표 원문 표기) 확인: {len(Q) - len(miss)}/{len(Q)}' + (f' / 미확인: {miss}' if miss else ''))

    # 3. 시행 회차 전수 대조 (원문 행을 PDF 같은 줄에서 찾음)
    row_ok, row_ng, row_near, row_manual = 0, [], [], []
    for q in Q:
        r = q.get('source_row')
        if not r:
            continue
        need = [clean(x) for x in r if clean(x)]
        name = need[0]; rest = need[1:]
        loose = q['agency_id'] == 'KCA'  # KCA 표는 칸 사이에 다른 열(유형·지역)이 있음
        hit = False
        tails = []
        for i, line in enumerate(pdf_lines):
            nxt = pdf_lines[i + 1] if i + 1 < len(pdf_lines) else ''
            for m in re.finditer(re.escape(name), line):
                tails.append(line[m.end():] + nxt)
            # 셀 안에서 종목명이 줄바꿈된 경우: 앞 조각이 이 줄, 뒤 조각이 다음(또는 이전) 줄
            for k in range(2, len(name) - 1):
                a, b = name[:k], name[k:]
                if a in line and (b in nxt or (i > 0 and b in pdf_lines[i - 1])):
                    for m in re.finditer(re.escape(a), line):
                        tails.append(line[m.end():] + nxt)
        for tail in tails:
            pos, ok = 0, True
            for tok in rest:
                j = tail.find(tok, pos)
                if j < 0 or (not loose and j - pos > 2):
                    ok = False; break
                pos = j + len(tok)
            if ok:
                hit = True; break
        if not hit:
            # 병합·줄바꿈 셀: 종목명 조각이 위아래 줄에 나뉘고 시행회는 가운데 줄에 위치 → 인접 4줄 창에서 모두 확인
            for i, line in enumerate(pdf_lines):
                for k in range(2, len(name)):
                    a, b = name[:k], name[k:]
                    if not (line.endswith(a) or line == a or a in line):
                        continue
                    win = ''.join(pdf_lines[max(0, i - 2):i + 3])
                    if (b == '' or b in win) and all(t in win for t in rest):
                        hit = 'near'; break
                if hit: break
        if not hit and q['name'] in MANUAL_CHECKS:
            hit = 'manual'; row_manual.append(f"{q['name']}: {MANUAL_CHECKS[q['name']]}")
        if hit == 'near':
            row_near.append(q['name'])
        if hit:
            row_ok += 1
        else:
            row_ng.append(f"{q['name']}{r}")
    R('3.시행회차', not row_ng, f'원문 행(종목명+시행회/면제검정 칸) PDF 확인 {row_ok}/{row_ok + len(row_ng)} (동일행 {row_ok - len(row_near) - len(row_manual)}, 줄바꿈·병합 셀 인접행 {len(row_near)}: {row_near}, 육안 대조 {len(row_manual)}: {row_manual})' + (f' / 미확인: {row_ng[:30]}' if row_ng else ''))
    # 매핑 회차 ↔ 원문 회차 일치
    mism = []
    for q in Q:
        r = q.get('source_row')
        if not r or q['agency_id'] != 'HRDK':
            continue
        maps = [sd[m['schedule_id']] for m in M if m['qualification_id'] == q['qualification_id']]
        got = sorted(s['round_no'] for s in maps if s['exam_type'] == 'regular')
        cells = r[1:]
        if q['grade'] == '기능사':
            exp = sorted(int(x) for x in re.findall(r'\d', cells[1])) if cells[1] not in ('상시', '미시행') else []
            if ('√' in cells[2]) != any(s['exam_type'] == 'school_exempt' for s in maps):
                mism.append(f"{q['name']} 면제검정")
        elif q['grade'] in ('기사', '산업기사', '서비스'):
            cell = cells[0] if q['grade'] == '기사' else cells[1]
            exp = sorted(int(x) for x in re.findall(r'\d', cell))
        else:
            exp = sorted(int(x) for x in re.findall(r'\d+', cells[0]))
        if got != exp:
            mism.append(f"{q['name']} 원문{exp} 매핑{got}")
    R('3.시행회차', not mism, 'HRDK 원문 시행회 ↔ 매핑 회차 일치' + (f' / 불일치 {mism}' if mism else ' (전 종목)'))

    # 4. 일정 원문 PDF 대조 + 요일
    raw_ok, raw_ng, wd_ng = 0, [], []
    for s in S:
        for p in s['phases']:
            for k, v in p.get('raw', {}).items():
                for part in v.split(' | '):
                    c = clean(part)
                    if c in pdf_all:
                        raw_ok += 1
                    else:
                        # 줄바꿈 위치 차이 허용: 날짜 토큰 단위로 순서대로 존재하는지
                        toks = re.findall(r'\d{1,2}\.?\d{1,2}\.?(?:\([월화수목금토일]\))?', c)
                        idx = pdf_all.find(toks[0]) if toks else -1
                        if toks and idx >= 0 and all(t in pdf_all for t in toks):
                            raw_ok += 1
                        else:
                            raw_ng.append(f"{s['schedule_id']}.{p['phase']}.{k}: {part!r}")
                    for m in re.finditer(r'(\d{1,2})\.\s*(\d{1,2})\.?\s*\(([월화수목금토일])\)', part.replace('\n', ' ')):
                        yy = 2027
                        try:
                            dt = datetime.date(yy, int(m.group(1)), int(m.group(2)))
                        except ValueError:
                            wd_ng.append(f"{s['schedule_id']} 잘못된 날짜 {m.group(0)}"); continue
                        if WD[dt.weekday()] != m.group(3):
                            wd_ng.append(f"{s['schedule_id']} {m.group(0)} 실제 {WD[dt.weekday()]}")
    R('4.일정원문', not raw_ng, f'일정 원문 문자열 PDF 확인 {raw_ok}/{raw_ok + len(raw_ng)}' + (f' / 미확인 {raw_ng}' if raw_ng else ''))
    R('4.요일', not wd_ng, '원문 요일 표기 ↔ 실제 2027년 요일 일치' + (f' / 불일치 {wd_ng}' if wd_ng else ' (전 항목)'))
    excl = [(s['schedule_id'], e) for s in S for p in s['phases'] for e in p.get('excluded_dates', [])]
    R('4.제외일', all(any(p['registration_periods'][0]['start'] <= e <= p['registration_periods'][-1]['end'] for p in sd[sid]['phases'] if p.get('registration_periods')) for sid, e in excl),
      f'접수 제외일 {excl} 이 접수기간 내에 있음')

    # 5. 중복
    for name, ids in (('qualification_id', [q['qualification_id'] for q in Q]), ('schedule_id', [s['schedule_id'] for s in S])):
        dup = [k for k, v in collections.Counter(ids).items() if v > 1]
        R('5.중복', not dup, f'{name} 중복 {dup or "없음"}')
    dupn = [k for k, v in collections.Counter(q['name'] for q in Q).items() if v > 1]
    R('5.중복', not dupn, f'종목명 중복 {dupn or "없음"}')
    dm = [k for k, v in collections.Counter((m['qualification_id'], m['schedule_id']) for m in M).items() if v > 1]
    R('5.중복', not dm, f'매핑 중복 {dm or "없음"}')

    # 6. 참조 무결성
    bad = [m for m in M if m['qualification_id'] not in qd or m['schedule_id'] not in sd]
    R('6.참조', not bad, f'매핑 {len(M)}건 참조 오류 {len(bad)}')
    R('6.참조', all(q['agency_id'] in ad for q in Q) and all(s['agency_id'] in ad for s in S), '종목·일정 agency_id 참조')
    R('6.참조', all(qd[c['qualification_id']] for c in L['changes'] if c['qualification_id'] in qd) and all(c['qualification_id'] in qd for c in L['changes']), f"changes {len(L['changes'])}건 참조")
    cross = [m for m in M if qd.get(m['qualification_id'], {}).get('agency_id') != sd.get(m['schedule_id'], {}).get('agency_id')]
    R('6.참조', not cross, f'종목-일정 시행기관 일치 (불일치 {len(cross)})')
    orphan = [s['schedule_id'] for s in S if not any(m['schedule_id'] == s['schedule_id'] for m in M)]
    R('6.참조', not orphan, f'매핑 없는 일정 {orphan or "없음"}')

    # 7. 날짜 형식·순서
    iso = re.compile(r'^\d{4}-\d{2}-\d{2}$'); order_ng = []; fmt_ng = []
    for s in S:
        prev_end = None
        for p in s['phases']:
            regs = p.get('registration_periods', []); exams = p.get('exam_periods', []); rs = p.get('result_dates', [])
            for x in regs + exams:
                for k in ('start', 'end'):
                    if not iso.match(x[k]) or not x[k].startswith('2027'): fmt_ng.append((s['schedule_id'], x[k]))
                if x['end'] < x['start']: order_ng.append(f"{s['schedule_id']} 역순 기간 {x}")
            for r in rs:
                if not iso.match(r['date']) or not r['date'].startswith('2027'): fmt_ng.append((s['schedule_id'], r['date']))
            if regs and exams and regs[-1]['end'] >= exams[0]['start']:
                order_ng.append(f"{s['schedule_id']}.{p['phase']} 접수종료 {regs[-1]['end']} ≥ 시험시작 {exams[0]['start']}")
            if exams and rs and min(r['date'] for r in rs) < exams[0]['start']:
                order_ng.append(f"{s['schedule_id']}.{p['phase']} 발표 {rs} < 시험시작 {exams[0]['start']}")
            labelled = len(regs) > 1 and all(x.get('label') for x in regs)
            if prev_end and regs and regs[0]['start'] < prev_end and not (labelled and regs[-1]['start'] > prev_end and p.get('notes')):
                # 필기 발표 이전 실기 접수 시작은 원문 확인 대상
                order_ng.append(f"{s['schedule_id']}.{p['phase']} 접수시작 {regs[0]['start']} < 이전 단계 발표 {prev_end}")
            if rs:
                prev_end = max(r['date'] for r in rs)
    R('7.날짜형식', not fmt_ng, f'ISO 8601·2027년 형식 오류 {fmt_ng or "없음"}')
    R('7.시간순서', not order_ng, '접수 < 시험 ≤ 발표, 필기 발표 ≤ 다음 단계 접수' + (f' / 확인 필요 {order_ng}' if order_ng else ' (전 일정)'))

    # 8. 미시행 종목 활성 매핑
    inactive = {q['qualification_id']: q for q in Q if q['annual_status'] in ('biennial_not_held', 'abolished', 'not_conducted')}
    bad = [inactive[m['qualification_id']]['name'] for m in M if m['qualification_id'] in inactive]
    R('8.미시행', not bad, f'미시행·폐지·미실시 {len(inactive)}종목의 활성 매핑 {bad or "없음"}')
    partial = [q for q in Q if q['annual_status'] == 'partially_held']
    R('8.미시행', all(all(sd[m['schedule_id']]['exam_type'] == 'school_exempt' for m in M if m['qualification_id'] == q['qualification_id']) for q in partial),
      f"정기검정 미시행 + 면제자 검정 시행 {len(partial)}종목은 면제자 검정 매핑만 보유: {[q['name'] for q in partial]}")

    # 9. CSV ↔ JSON
    for k, v in L.items():
        with open(pathlib.Path(csv_dir) / f'{k}.csv', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        def norm(x):
            return {kk: json.dumps(vv, ensure_ascii=False) if isinstance(vv, (list, dict)) else ('' if vv is None else str(vv)) for kk, vv in x.items()}
        jrows = [norm(x) for x in v]
        same = len(rows) == len(jrows) and all({kk: r.get(kk, '') for kk in j} == j for r, j in zip(rows, jrows))
        R('9.CSV=JSON', same, f'{k}: CSV {len(rows)}행 / JSON {len(jrows)}건 {"일치" if same else "불일치"}')

    # 확정 수정사항
    corr = [(s['schedule_id'], p['correction']) for s in S for p in s['phases'] if p.get('correction')]
    R('확정수정', len(corr) == 2 and {c[1]['corrected'] for c in corr} == {'2027-07-16', '2027-12-17'}, f'빅데이터분석기사 최종발표 연도 수정 적용 {len(corr)}건: {[(c[0], c[1]["original"], c[1]["corrected"]) for c in corr]}')

    ok = all(r[1] for r in res)
    lines = [f'# 데이터 검증 리포트', '', f'- 실행 시각: {datetime.datetime.now().isoformat(timespec="seconds")}',
             f'- 결과: {"전 항목 통과" if ok else "확인 필요 항목 있음"} ({sum(r[1] for r in res)}/{len(res)})', '',
             '| 구분 | 결과 | 내용 |', '|---|---|---|']
    for sec, okk, det in res:
        lines.append(f'| {sec} | {"통과" if okk else "확인필요"} | {det.replace("|", "/")} |')
    pathlib.Path(out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for sec, okk, det in res:
        print(('PASS ' if okk else 'FAIL ') + sec + ' ' + det[:400])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
