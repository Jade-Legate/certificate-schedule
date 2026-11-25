"""2027 국가기술자격 시험일정 데이터 빌드 (HWPX 원본 → 정규화 JSON/CSV).

사용: python3 -I scripts/build_data.py <detail.hwpx> <summary.hwpx> <out_dir>
  - out_dir/data/2027/{qualifications,schedules,mappings,agencies,changes}.json
  - out_dir/csv/*.csv           (JSON과 동일 레코드, validate.py 가 일치 검사)
  - out_dir/review/review_items.json  (자동 생성 검수 목록)

원칙
  * 날짜는 원문 문자열(raw)을 함께 보존한다.
  * 공식 자료 오류 의심 항목은 수정하지 않고 review_items 로 남긴다.
  * 예외: 빅데이터분석기사 최종 발표 연도 (프로젝트 담당자 확정 수정, OVERRIDES 참조)
"""
import sys, os, json, csv, re, hashlib, pathlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwpx_tables import extract
import table_specs
from types import SimpleNamespace
from dates import parse_cell

YEAR = 2027
SRC_DETAIL = '2027년 국가기술자격 검정시행계획(상세)'
SRC_SUMMARY = '2027년 국가기술자격 검정시행계획(요약)'

GRADES = {  # code, label, order
    '기술사': ('pe', 1), '기능장': ('master', 2), '기사': ('engineer', 3),
    '산업기사': ('industrial', 4), '서비스': ('service', 5), '기능사': ('craft', 6)}

AGENCIES = [
    dict(agency_id='HRDK', name='한국산업인력공단', site_name='큐넷(Q-Net)', official_url='https://www.q-net.or.kr/',
         registration_url='https://www.q-net.or.kr/'),
    dict(agency_id='KCCI', name='대한상공회의소', site_name='대한상공회의소 자격평가사업단',
         official_url='https://license.korcham.net/', registration_url='https://license.korcham.net/'),
    dict(agency_id='KINS', name='한국원자력안전기술원', site_name='한국원자력안전기술원',
         official_url='https://www.kins.re.kr/', registration_url=None),
    dict(agency_id='KOFIC', name='영화진흥위원회', site_name='영화진흥위원회',
         official_url='https://www.kofic.or.kr/', registration_url=None),
    dict(agency_id='KOCCA', name='한국콘텐츠진흥원', site_name='게임국가기술자격검정',
         official_url='https://www.kgq.or.kr/', registration_url='https://www.kgq.or.kr/'),
    dict(agency_id='KCA', name='한국방송통신전파진흥원', site_name='국가기술자격검정(CQ-Net)',
         official_url='https://www.cq.or.kr/', registration_url='https://www.cq.or.kr/'),
    dict(agency_id='KOMIR', name='한국광해광업공단', site_name='광해광업 자격검정(MQ-Net)',
         official_url='https://www.mq-net.or.kr/', registration_url='https://www.mq-net.or.kr/'),
    dict(agency_id='KDATA', name='한국데이터산업진흥원', site_name='데이터자격검정(DataQ)',
         official_url='https://www.dataq.or.kr/', registration_url='https://www.dataq.or.kr/'),
    dict(agency_id='KIDP', name='한국디자인진흥원', site_name='디자인 자격검정',
         official_url='https://designq.kidp.or.kr/', registration_url='https://designq.kidp.or.kr/'),
    dict(agency_id='KOSHA', name='한국산업안전보건공단', site_name='한국산업안전보건공단',
         official_url='https://www.kosha.or.kr/', registration_url=None),
]

# 확정 수정사항 (프로젝트 담당자 확인 완료, 추가 확인 불필요)
OVERRIDES = {
    ('KDATA', '제14회', 'practical', 'result'): dict(value='2027-07-16', original='’26.7.16',
        reason='공식 자료에 2026년으로 기재되었으나 실기시험(2027-06-26) 이후 발표이므로 2027년 오기로 판단. 프로젝트 담당자 확인 후 수정 확정.'),
    ('KDATA', '제15회', 'practical', 'result'): dict(value='2027-12-17', original='’26.12.17',
        reason='공식 자료에 2026년으로 기재되었으나 실기시험(2027-11-27) 이후 발표이므로 2027년 오기로 판단. 프로젝트 담당자 확인 후 수정 확정.'),
}

review = []  # 자동 검수 목록


def rv(kind, ref, detail, severity='check'):
    review.append(dict(kind=kind, source_reference=ref, detail=detail, severity=severity))


def clean(s):
    return re.sub(r'\s+', '', (s or '').replace('⏎', ''))


def qid(name):
    return 'Q' + hashlib.sha1(name.encode('utf-8')).hexdigest()[:8].upper()


# ---------------------------------------------------------------- tables
def tables_by_id(path):
    t, _ = extract(path)
    return {x['table_id']: x['rows'] for x in t}, t


# 공고 표 위치(표 ID)는 main()에서 table_specs 로 내용 기반 탐색 후 채운다. (D: 상세, SM: 요약)
D = SimpleNamespace()
SM = SimpleNamespace()
STRICT_KINDS = {'count', 'name_lookup', 'table'}  # 이 종류의 error 가 하나라도 있으면 빌드 실패


def pilda_day(tables, tid):
    """'□ ‘27. 11. 6.(토) 시행 종목' 같은 소제목에서 날짜를 읽는다. 연도가 다르면 빌드 실패."""
    h = table_specs.heading_of(tables, tid)
    m = re.search(r'(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', h)
    if not m or 2000 + int(m.group(1)) != YEAR:
        raise SystemExit(f'필답형 시행일 소제목을 읽지 못했습니다: {tid} {h!r}')
    return f'{YEAR}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'


# ---------------------------------------------------------------- schedule helpers
schedules = {}


def phase_obj(phase, reg=None, exam=None, result=None, ref=None, docs=None, extra_notes=None, key=None, ov_scope=None):
    out = {'phase': phase, 'raw': {}}
    for k, raw in (('registration', reg), ('exam', exam), ('result', result), ('document_submission', docs)):
        if raw is None or raw == '':
            continue
        if isinstance(raw, list):  # 이미 구조화된 복수 기간
            out[k + '_periods' if k != 'result' else 'result_dates'] = raw
            continue
        out['raw'][k] = raw
        p = parse_cell(raw, YEAR)
        for iss in p['issues']:
            rv('date_parse', ref, f'{phase}.{k}: {iss}', 'error' if 'mismatch' in iss or 'invalid' in iss else 'check')
        if k == 'result':
            out['result_dates'] = [{'date': x['start'], **({'label': x['label']} if 'label' in x else {})} for x in p['periods']]
        elif k == 'document_submission':
            out['document_submission'] = p['periods'][0] if p['periods'] else None
        else:
            out[k + '_periods'] = [{'start': x['start'], 'end': x['end'], **({'label': x['label']} if 'label' in x else {})} for x in p['periods']]
        if p['excluded']:
            out.setdefault('excluded_dates', []).extend(p['excluded'])
        if ov_scope:
            ov = OVERRIDES.get((*ov_scope, phase, k))
            if ov:
                out['result_dates'] = [{'date': ov['value']}]
                out['correction'] = {'field': 'result_dates', 'original': ov['original'], 'corrected': ov['value'], 'reason': ov['reason']}
    if extra_notes:
        out['notes'] = extra_notes
    return out


def add_schedule(sid, agency, exam_type, group, round_label, phases, ref, notes=None, status='published', round_no=None):
    if sid in schedules:
        raise SystemExit(f'duplicate schedule id {sid}')
    schedules[sid] = dict(schedule_id=sid, year=YEAR, agency_id=agency, exam_type=exam_type, schedule_group=group,
                          round=round_label, round_no=round_no, phases=phases, publication_status=status,
                          source_reference=ref, notes=notes or [])
    return sid


# ---------------------------------------------------------------- qualifications
quals = {}
mappings = []
changes = []


def add_qual(name, grade, agency, ref, field=None, aliases=None, annual_status='scheduled', exam_types=None,
             written_exam=True, status_reason=None, source_row=None):
    i = qid(name)
    if i in quals:
        raise SystemExit(f'duplicate qualification {name}')
    quals[i] = dict(qualification_id=i, name=name, grade=grade, grade_code=GRADES[grade][0], agency_id=agency,
                    field=field, aliases=aliases or [], exam_types=exam_types or [], annual_status=annual_status,
                    status_reason=status_reason, has_written_exam=written_exam, source_reference=ref,
                    source_row=source_row)
    return i


def add_map(q, sid, ref, eligibility_note=None, override=None, verification='verified'):
    m = dict(qualification_id=q, schedule_id=sid, eligibility_note=eligibility_note, override=override,
             verification=verification, source_reference=ref)
    mappings.append(m)
    et = schedules[sid]['exam_type']
    if et not in quals[q]['exam_types']:
        quals[q]['exam_types'].append(et)


def rounds_of(cell):
    cell = (cell or '').replace('‧', '·').replace(',', '·')
    return [int(x) for x in re.findall(r'\d+', cell)]


# ================================================================= HRDK
def build_hrdk(T, S):
    ref = lambda t, r=None: f'상세:{t}' + (f':r{r}' if r is not None else '')
    common_hrdk = ['원서접수 시간: 첫날 10:00 ~ 마지막 날 18:00 (일부 시험은 지역별·등급별 분산 접수 가능)',
                   '필기 합격(예정)자 및 최종합격자 발표 시간: 발표일 09:00',
                   'Q-Net 차세대 시스템 구축으로 2027.10.8.(금) 18:00 ~ 10.18.(월) 09:00 원서접수·환불 등 서비스 중단']
    two_stage = '실기 최종합격자 발표는 채점방식에 따라 1차(현지채점 종목)·2차(중앙채점·복합형 종목)로 나뉩니다. 종목별 해당 여부는 큐넷에서 확인하세요.'
    # --- 기술사 (D.hrdk_pe_sched): 회차당 2행(면접 접수 2회)
    t = T[D.hrdk_pe_sched]
    pe_notes = {141: '2025년 제135회 필기 합격자는 ① 3.8.~3.11. 기간에만 접수할 수 있습니다.',
                142: '2025년 제136회 필기 합격자는 ① 6.21.~6.24. 기간에만 접수할 수 있습니다.',
                143: '2025년 제137회 필기 합격자는 ① 9.20.~9.23. 기간에만 접수할 수 있습니다.'}
    rows = [r for r in t[2:]]
    for i in range(0, len(rows), 2):
        a, b = rows[i], rows[i + 1]
        rn = int(re.search(r'\d+', a[0]).group())
        r1 = parse_cell(a[6])['periods'][0]; r2 = parse_cell(b[6])['periods'][0]
        regs = [dict(r1, label='①'), dict(r2, label='②')]
        w = phase_obj('written', a[1], a[2], a[3], ref(D.hrdk_pe_sched, i + 2), docs=a[4])
        w['eligibility_reference_date'] = parse_cell(a[5])['periods'][0]['start']
        iv = phase_obj('interview', None, a[7], a[8], ref(D.hrdk_pe_sched, i + 2))
        iv['registration_periods'] = regs
        iv['raw']['registration'] = a[6] + ' | ' + b[6]
        iv['notes'] = ['면접시험 원서접수는 두 차례 진행됩니다.', pe_notes[rn]]
        add_schedule(f'HRDK-PE-{rn}', 'HRDK', 'regular', 'HRDK-기술사', f'제{rn}회', [w, iv],
                     ref(D.hrdk_pe_sched, f'{i+2}-{i+3}'), common_hrdk, round_no=rn)
    # --- 기능장 (D.hrdk_ma_sched)
    for ri, r in enumerate(T[D.hrdk_ma_sched][2:], 2):
        rn = int(re.search(r'\d+', r[0]).group())
        w = phase_obj('written', r[1], r[2], r[3], ref(D.hrdk_ma_sched, ri), docs=r[4])
        w['eligibility_reference_date'] = parse_cell(r[5])['periods'][0]['start']
        p = phase_obj('practical', r[6], r[7], r[8], ref(D.hrdk_ma_sched, ri), extra_notes=[two_stage])
        add_schedule(f'HRDK-MA-{rn}', 'HRDK', 'regular', 'HRDK-기능장', f'제{rn}회', [w, p], ref(D.hrdk_ma_sched, ri), common_hrdk, round_no=rn)
    # --- 기사·산업기사·서비스 (D.hrdk_en_sched)
    for ri, r in enumerate(T[D.hrdk_en_sched][2:], 2):
        rn = int(re.search(r'\d+', r[0]).group())
        w = phase_obj('written', r[1], r[2], r[3], ref(D.hrdk_en_sched, ri), docs=r[4])
        w['eligibility_reference_date'] = parse_cell(r[5])['periods'][0]['start']
        notes = [two_stage]
        if rn == 3:
            notes.append('기사 제3회 필답형 실기시험은 11.6.(토)·11.14.(일) 2일 분산 시행 (종목별 시험일은 아래 종목별 안내 참고)')
        else:
            notes.append({1: '필답형 실기시험일: 4.18.(일)', 2: '필답형 실기시험일: 7.10.(토)'}[rn])
        p = phase_obj('practical', r[6], r[7], r[8], ref(D.hrdk_en_sched, ri), extra_notes=notes)
        add_schedule(f'HRDK-EN-{rn}', 'HRDK', 'regular', 'HRDK-기사·산업기사·서비스', f'제{rn}회', [w, p], ref(D.hrdk_en_sched, ri), common_hrdk, round_no=rn)
    # --- 기능사 (D.hrdk_cr_sched) + 면제자 검정
    pilda = {1: '3.14.(일)', 2: '5.29.(토)', 3: '8.28.(토)', 4: '11.28.(일)'}
    for ri, r in enumerate(T[D.hrdk_cr_sched][2:], 2):
        if '면제자' in r[1]:
            p = phase_obj('practical', r[4], r[5], r[6], ref(D.hrdk_cr_sched, ri),
                          extra_notes=['필답형 실기시험은 시험이 시작되는 첫 번째 평일 6.14.(월) 시행', two_stage])
            add_schedule('HRDK-CR-SCHOOL', 'HRDK', 'school_exempt', 'HRDK-기능사', '필기시험 면제자 검정', [p], ref(D.hrdk_cr_sched, ri),
                         common_hrdk + ['산업수요 맞춤형 고등학교 및 특성화고 등 필기시험 면제자 대상 별도 검정 (일반 필기시험 면제자 응시 불가)'])
            continue
        rn = int(re.search(r'\d+', r[0]).group())
        w = phase_obj('written', r[1], r[2], r[3], ref(D.hrdk_cr_sched, ri))
        p = phase_obj('practical', r[4], r[5], r[6], ref(D.hrdk_cr_sched, ri), extra_notes=[f'필답형 실기시험일: {pilda[rn]}', two_stage])
        add_schedule(f'HRDK-CR-{rn}', 'HRDK', 'regular', 'HRDK-기능사', f'제{rn}회', [w, p], ref(D.hrdk_cr_sched, ri), common_hrdk, round_no=rn)
    add_schedule('HRDK-ROLLING', 'HRDK', 'rolling', 'HRDK-상시', '상시검정', [], '상세:본문 3.다(상시검정 시행계획)',
                 ['연초 준비기간 및 동절기 등 일부 기간을 제외하고 연중 상시 시행',
                  '시행지역별 시험장 여건과 수험인원을 고려해 별도 시험 일정을 정해 시행',
                  '상시검정 세부 시행계획은 큐넷 누리집에 공고'], status='agency_announcement')

    # --- 종목 마스터
    biennial = {clean(x) for x in re.split(r'[,，]', ','.join(r[1] for r in T[D.biennial_skip][1:]))}
    abolished = {'포장산업기사', '석공예기능사'}

    def note_bi(name):
        return name in biennial

    # 기술사
    for r in T[D.hrdk_pe_items][1:]:
        for f, n, rr in ((r[0], r[1], r[2]), (r[4], r[5], r[6])):
            if not n: continue
            name = clean(n) + '기술사'
            q = add_qual(name, '기술사', 'HRDK', f'HRDK 상세:{D.hrdk_pe_items}', clean(f), source_row=[n, rr])
            for x in rounds_of(rr):
                add_map(q, f'HRDK-PE-{x}', f'상세:{D.hrdk_pe_items} 시행회 {rr}')
    # 기능장
    for r in T[D.hrdk_ma_items][1:]:
        for f, n, rr in ((r[0], r[1], r[2]), (r[4], r[5], r[6])):
            if not n: continue
            base = clean(n)
            name = {'미용': '미용장', '이용': '이용장'}.get(base, base + '기능장')
            q = add_qual(name, '기능장', 'HRDK', f'HRDK 상세:{D.hrdk_ma_items}', clean(f), source_row=[n, rr])
            for x in rounds_of(rr):
                add_map(q, f'HRDK-MA-{rn_ma(x)}', f'상세:{D.hrdk_ma_items} 시행회 {rr}')
    # 기사·산업기사·서비스
    svc_re = re.compile(r'(사\d급|관리사|분석사|상담사|심리사|기획사|전문가|코디네이터)$')
    for tid in D.hrdk_en_items:
        for r in T[tid][2:]:
            for f, n, en, ie in ((r[0], r[1], r[2], r[3]), (r[5], r[6], r[7], r[8])):
                if not n: continue
                base = clean(n)
                for g, cell in (('기사', en), ('산업기사', ie)):
                    cell = (cell or '').strip()
                    if cell in ('♤', ''):
                        continue
                    grade = g
                    if g == '산업기사' and svc_re.search(base):
                        grade, name = '서비스', base
                    else:
                        m = re.match(r'^(.*?)(\(.*\))$', base)
                        name = (m.group(1) + g + m.group(2)) if m else base + g
                    if name in abolished:
                        continue
                    if cell == '미시행':
                        if not note_bi(name):
                            rv('status_conflict', f'상세:{tid}', f'{name}: 종목표 미시행이나 별첨3 홀수연도 미시행 목록에 없음', 'error')
                        add_qual(name, grade, 'HRDK', f'HRDK 상세:{tid}', clean(f), annual_status='biennial_not_held', source_row=[n, en, ie],
                                 status_reason='검정시행 조정제도(격년 시행)에 따라 2027년 필기·실기 미시행, 2028년 시행 예정')
                        continue
                    q = add_qual(name, grade, 'HRDK', f'HRDK 상세:{tid}', clean(f), source_row=[n, en, ie])
                    for x in rounds_of(cell):
                        add_map(q, f'HRDK-EN-{x}', f'상세:{tid} 시행회 {cell}')
    # 기능사
    rolling_names = {'지게차운전', '굴착기운전', '미용(일반)', '미용(피부)', '미용(네일)', '미용(메이크업)', '한식조리', '양식조리',
                     '중식조리', '일식조리', '제과', '제빵', '건축도장', '방수'}
    for tid in D.hrdk_cr_items:
        for r in T[tid][2:]:
            for f, n, gb, gen, ex in ((r[0], r[1], r[2], r[3], r[4]), (r[6], r[7], r[8], r[9], r[10])):
                if not n: continue
                base = clean(n).replace('‧', '·')
                if base.startswith('미용('):
                    name = '미용사' + base[2:]
                elif base == '이용':
                    name = '이용사'
                else:
                    m = re.match(r'^(.*?)(\(.*\))$', base)
                    name = (m.group(1) + '기능사' + m.group(2)) if m else base + '기능사'
                no_written = (gb or '').strip() == '-'
                gen = (gen or '').strip(); school = (ex or '').strip() == '√'
                if gen == '미시행':
                    if name not in biennial:
                        rv('status_conflict', f'상세:{tid}', f'{name}: 미시행이나 격년 목록에 없음', 'error')
                    q = add_qual(name, '기능사', 'HRDK', f'HRDK 상세:{tid}', clean(f), annual_status='biennial_not_held', source_row=[n, gb or '', gen, ex or ''],
                                 written_exam=not no_written,
                                 status_reason='검정시행 조정제도(격년 시행)에 따라 2027년 정기검정 필기·실기 미시행, 2028년 시행 예정')
                    if school:
                        quals[q]['annual_status'] = 'partially_held'
                        add_map(q, 'HRDK-CR-SCHOOL', f'상세:{tid} 면제검정 √ + 별첨3 기타사항',
                                eligibility_note='격년 시행은 검정형 정기시험에만 적용되며, 산업수요 맞춤형 고등학교 및 특성화고 등 필기시험 면제자 검정은 정상 시행(별첨3 기타사항).')
                        rv('interpretation', f'상세:{tid}', f'{name}: 정기검정 미시행·면제자 검정 시행으로 해석(종목표 √ + 별첨3 "필기시험 면제자 검정은 정상 시행됨"). 기존 v2 데이터는 매핑 제외였음.', 'info')
                    continue
                q = add_qual(name, '기능사', 'HRDK', f'HRDK 상세:{tid}', clean(f), written_exam=not no_written, source_row=[n, gb or '', gen, ex or ''])
                ov = {'phases_excluded': ['written']} if no_written else None
                if gen == '상시':
                    add_map(q, 'HRDK-ROLLING', f'상세:{tid} 시행회 상시')
                else:
                    for x in rounds_of(gen):
                        add_map(q, f'HRDK-CR-{x}', f'상세:{tid} 시행회 {gen}', override=ov)
                    if base in rolling_names:
                        add_map(q, 'HRDK-ROLLING', '상세:본문 1.다.3) 상시검정 14종목',
                                eligibility_note='정기검정과 상시검정을 모두 시행하는 종목입니다.')
                if school:
                    add_map(q, 'HRDK-CR-SCHOOL', f'상세:{tid} 면제검정 √', override=ov)
                if base in rolling_names and gen == '상시':
                    pass
    # 상시 14종목 검증
    rolling_q = {m['qualification_id'] for m in mappings if m['schedule_id'] == 'HRDK-ROLLING'}
    if len(rolling_q) != 14:
        rv('count', '상세:본문 상시 14종목', f'상시검정 매핑 {len(rolling_q)}건 (기대 14)', 'error')
    # 폐지
    for n, g in (('포장산업기사', '산업기사'), ('석공예기능사', '기능사')):
        add_qual(n, g, 'HRDK', f'요약:{SM.abolished} 폐지 종목', annual_status='abolished', status_reason='2027년 폐지 종목')
        changes.append(dict(qualification_id=qid(n), year=YEAR, annual_status='abolished', change_type='abolished',
                            reason='2027년 폐지 (소관부처: 산업통상부)', source_reference=f'요약:{SM.abolished}; 상세:{D.hrdk_summary}'))
    # 기사 제3회 필답형 종목별 시험일 (별첨2)
    by_name = {v['name']: k for k, v in quals.items()}
    for tid, day in D.pilda_days:
        for r in T[tid][1:]:
            n = clean(r[3]); part = r[2].strip()
            old = re.search(r'\(구\.(.+?)\)$', n)
            if old:
                n = n[:old.start()]
                if by_name.get(n) and old.group(1) not in quals[by_name[n]]['aliases']:
                    quals[by_name[n]]['aliases'].append(old.group(1))
            k = by_name.get(n)
            if not k:
                rv('name_lookup', f'상세:{tid}', f'별첨2 종목명 {n} 이 종목 마스터에 없음', 'error'); continue
            hit = [m for m in mappings if m['qualification_id'] == k and m['schedule_id'] == 'HRDK-EN-3']
            if not hit:
                rv('mapping', f'상세:{tid}', f'{n}: 별첨2 기사 제3회 필답형 대상이나 제3회 시행회 매핑 없음', 'error'); continue
            hit[0]['override'] = {'practical_written_exam_date': day, 'practical_written_exam_part': part,
                                  'note': f'제3회 필답형 실기시험일: {day[5:7].lstrip("0")}.{day[8:].lstrip("0")}.({"토" if day.endswith("06") else "일"}) {part}'}
    return


def rn_ma(x):
    return x


# ================================================================= 기타 기관
def build_others(T):
    # ---- KCCI 정기
    t = T[D.kcci_sched]
    kcci_common = ['정기검정 시행지역: 서울, 부산, 대구, 인천, 광주, 대전, 제주 등 주요 상공회의소']
    for ri, r in enumerate(t[1:], 1):
        pass
    sok = {1: t[1], 2: t[2]}
    for rn, r in sok.items():
        add_schedule(f'KCCI-SOKGI-{rn}', 'KCCI', 'regular', 'KCCI-한글속기', f'{rn}회',
                     [phase_obj('practical', r[4], r[5], r[6], f'상세:{D.kcci_sched}:r{rn}')], f'상세:{D.kcci_sched}:r{rn}', kcci_common, round_no=rn)
    for name_key, rows, sid in (('전자상거래관리사', (3, 4), 'KCCI-ECM-1'), ('전자상거래운용사', (5, 6), 'KCCI-ECO-1')):
        w, p = t[rows[0]], t[rows[1]]
        notes = list(kcci_common)
        if sid == 'KCCI-ECM-1':
            notes.append('전자상거래관리사 2급 실기시험 출제형태는 작업형에서 필답형으로 변경 시행')
        add_schedule(sid, 'KCCI', 'regular', 'KCCI-' + name_key, '1회',
                     [phase_obj('written', w[4], w[5], w[6], f'상세:{D.kcci_sched}:r{rows[0]}'),
                      phase_obj('practical', p[4], p[5], p[6], f'상세:{D.kcci_sched}:r{rows[1]}')], f'상세:{D.kcci_sched}:r{rows[0]}-{rows[1]}', notes, round_no=1)
    for g in (1, 2, 3):
        q = add_qual(f'한글속기 {g}급', '서비스', 'KCCI', f'상세:{D.kcci_sched}')
        for rn in (1, 2): add_map(q, f'KCCI-SOKGI-{rn}', f'상세:{D.kcci_sched}')
    q = add_qual('전자상거래관리사 2급', '서비스', 'KCCI', f'상세:{D.kcci_sched}'); add_map(q, 'KCCI-ECM-1', f'상세:{D.kcci_sched}')
    q = add_qual('전자상거래운용사', '서비스', 'KCCI', f'상세:{D.kcci_sched}'); add_map(q, 'KCCI-ECO-1', f'상세:{D.kcci_sched}')
    add_qual('전자상거래관리사 1급', '서비스', 'KCCI', '상세:본문 대한상공회의소 3.나.2)', annual_status='biennial_not_held',
             status_reason='검정시행 조정제도(격년 시행)에 따라 2027년 필기·실기 미시행')
    # ---- KCCI 상시
    res = T[D.kcci_roll][1][6]
    roll_notes = ['원서접수: 개설일로부터 시험일 4일 전까지', '시험일: 상시검정 시행 상공회의소가 정하는 일자',
                  '합격자 발표: ' + res.replace('\n', ' ')]
    add_schedule('KCCI-ROLLING', 'KCCI', 'rolling', 'KCCI-상시', '상시검정', [], f'상세:{D.kcci_roll}', roll_notes, status='agency_announcement')
    sep = '수험인원과 시행지역별 시험장 여건 등을 고려해 별도 시험 일정을 정하여 시행합니다.'
    biseo = {1: '비서 1급 실기: 워드프로세서, 컴퓨터활용능력 1·2급, 한글속기 1·2급, 전산회계운용사 1·2급 중 택일',
             2: '비서 2급 실기: 워드프로세서, 컴퓨터활용능력 1·2급, 한글속기 1·2급, 전산회계운용사 1·2급 중 택일',
             3: '비서 3급 실기: 워드프로세서, 컴퓨터활용능력 1·2급, 한글속기 1·2·3급, 전산회계운용사 1·2·3급 중 택일'}
    for name, note in [('워드프로세서', None), ('컴퓨터활용능력 1급', None), ('컴퓨터활용능력 2급', None),
                       ('전산회계운용사 1급', sep), ('전산회계운용사 2급', None), ('전산회계운용사 3급', None),
                       ('비서 1급', sep + ' ' + biseo[1]), ('비서 2급', sep + ' ' + biseo[2]), ('비서 3급', sep + ' ' + biseo[3]),
                       ('경영정보시각화능력', sep + ' 실기 합격자 발표: 시험일로부터 41일 후 금요일 10:00')]:
        aliases = {'컴퓨터활용능력 1급': ['컴활 1급', '컴활1급', '컴활'], '컴퓨터활용능력 2급': ['컴활 2급', '컴활2급', '컴활'],
                   '워드프로세서': ['워드'], '전산회계운용사 1급': ['전산회계'], '전산회계운용사 2급': ['전산회계'],
                   '전산회계운용사 3급': ['전산회계']}.get(name, [])
        q = add_qual(name, '서비스', 'KCCI', f'상세:{D.kcci_roll}', aliases=aliases)
        add_map(q, 'KCCI-ROLLING', f'상세:{D.kcci_roll}', eligibility_note=note)
    # ---- KINS
    kins_n = ['원서접수 시간: 첫날 09:00 ~ 마지막 날 18:00', '시행일정은 타 면허시험 일정에 따라 조정될 수 있음']
    r1, r2 = T[D.kins_pe][1], T[D.kins_pe][2]
    add_schedule('KINS-PE-1', 'KINS', 'regular', 'KINS-기술사', '1회',
                 [phase_obj('written', r1[2], r1[3], r1[4], f'상세:{D.kins_pe}:r1'), phase_obj('interview', r2[2], r2[3], r2[4], f'상세:{D.kins_pe}:r2')],
                 f'상세:{D.kins_pe}', kins_n, round_no=1)
    r1, r2 = T[D.kins_en][1], T[D.kins_en][2]
    add_schedule('KINS-EN-1', 'KINS', 'regular', 'KINS-기사', '1회',
                 [phase_obj('written', r1[2], r1[3], r1[4], f'상세:{D.kins_en}:r1'), phase_obj('practical', r2[2], r2[3], r2[4], f'상세:{D.kins_en}:r2')],
                 f'상세:{D.kins_en}', kins_n, round_no=1)
    for n in ('방사선관리기술사', '원자력발전기술사'):
        add_map(add_qual(n, '기술사', 'KINS', f'상세:{D.kins_pe}'), 'KINS-PE-1', f'상세:{D.kins_pe}')
    add_map(add_qual('원자력기사', '기사', 'KINS', f'상세:{D.kins_en}'), 'KINS-EN-1', f'상세:{D.kins_en}')
    # ---- KOFIC
    kofic_n = ['원서접수 시간: 첫날 09:00 ~ 마감일 18:00', '필기·최종합격자 발표 시간: 발표일 10:00', '필기시험 토요일 시행, 시행지역: 부산']
    for tid, sid, name, g in ((D.kofic_in, 'KOFIC-IN-1', '영사산업기사', '산업기사'), (D.kofic_cr, 'KOFIC-CR-1', '영사기능사', '기능사')):
        r = T[tid][1]
        add_schedule(sid, 'KOFIC', 'regular', 'KOFIC-' + name, '제1회',
                     [phase_obj('written', r[1], r[2], r[3], f'상세:{tid}:r1'), phase_obj('practical', r[4], r[5], r[6], f'상세:{tid}:r1')],
                     f'상세:{tid}', kofic_n, round_no=1)
        add_map(add_qual(name, g, 'KOFIC', f'상세:{tid}'), sid, f'상세:{tid}')
    # ---- KOCCA
    r = T[D.kocca][1]
    add_schedule('KOCCA-1', 'KOCCA', 'regular', 'KOCCA-게임', '제1회',
                 [phase_obj('written', r[1], r[2], r[3], f'상세:{D.kocca}:r1'), phase_obj('practical', r[4], r[5], r[6], f'상세:{D.kocca}:r1')],
                 f'상세:{D.kocca}', ['원서접수 시간: 첫날 10:00 ~ 마지막 날 16:00', '합격자 발표 시간: 발표일 10:00',
                               '시행지역: 서울, 대전, 광주, 부산, 제주 (응시자 10명 미만 검정장은 근접지역과 통합 운영)'], round_no=1)
    for n in ('게임기획전문가', '게임그래픽전문가', '게임프로그래밍전문가'):
        add_map(add_qual(n, '서비스', 'KOCCA', f'상세:{D.kocca}'), 'KOCCA-1', f'상세:{D.kocca}')
    # ---- KOMIR
    komir_n = ['원서접수 시간: 첫날 09:00 ~ 마지막 날 18:00', '합격자 발표 시간: 발표일 10:00부터']
    seen = collections.Counter()
    for ri, r in enumerate(T[D.komir][1:], 1):
        g = r[0].strip(); base = clean(r[1]); name = base + g
        seen[name] += 1; rn = seen[name]
        sid = f'KOMIR-{qid(name)}-{rn}'
        add_schedule(sid, 'KOMIR', 'regular', 'KOMIR-' + name, f'{rn}회',
                     [phase_obj('written', r[2], r[3], r[4], f'상세:{D.komir}:r{ri}'), phase_obj('practical', r[5], r[6], r[7], f'상세:{D.komir}:r{ri}')],
                     f'상세:{D.komir}:r{ri}', komir_n, round_no=rn)
        k = qid(name)
        if k not in quals:
            add_qual(name, g, 'KOMIR', f'상세:{D.komir}')
        add_map(k, sid, f'상세:{D.komir}:r{ri}')
    # ---- KDATA (빅데이터분석기사) — 확정 수정 적용
    for ri, r in enumerate(T[D.kdata][1:], 1):
        rl = r[0].strip(); rn = int(re.search(r'\d+', rl).group())
        add_schedule(f'KDATA-{rn}', 'KDATA', 'regular', 'KDATA-빅데이터분석기사', rl,
                     [phase_obj('written', r[1], r[2], r[3], f'상세:{D.kdata}:r{ri}', ov_scope=('KDATA', rl)),
                      phase_obj('practical', r[4], r[5], r[6], f'상세:{D.kdata}:r{ri}', ov_scope=('KDATA', rl))],
                     f'상세:{D.kdata}:r{ri}', ['원서접수 시간: 첫날 10:00 ~ 마지막 날 18:00', '합격자 발표 시간: 발표일 10:00',
                                          '검정수수료: 필기 17,800원 / 실기 40,800원'], round_no=rn)
    q = add_qual('빅데이터분석기사', '기사', 'KDATA', f'상세:{D.kdata}')
    add_map(q, 'KDATA-14', f'상세:{D.kdata}:r1'); add_map(q, 'KDATA-15', f'상세:{D.kdata}:r2')
    # ---- KIDP
    r = T[D.kidp][1]
    add_schedule('KIDP-8', 'KIDP', 'regular', 'KIDP-서비스·경험디자인기사', '제8회',
                 [phase_obj('written', r[1], r[2], r[3], f'상세:{D.kidp}:r1'), phase_obj('practical', r[4], r[5], r[6], f'상세:{D.kidp}:r1')],
                 f'상세:{D.kidp}', ['원서접수 시간: 첫날 10:00 ~ 마지막 날 16:00', '합격자 발표 시간: 발표일 16:00부터',
                               '시행지역: 서울 / 수수료: 필기 22,000원, 실기 35,200원'], round_no=8)
    add_map(add_qual('서비스·경험디자인기사', '기사', 'KIDP', f'상세:{D.kidp}', aliases=['서비스경험디자인기사']), 'KIDP-8', f'상세:{D.kidp}')
    # ---- KOSHA
    add_qual('타워크레인설치해체기능사', '기능사', 'KOSHA', f'요약:{SM.agencies} 각주', annual_status='not_conducted',
             status_reason='한국산업안전보건공단 기관 내부사정으로 2027년 검정형 시험 미실시')


# ================================================================= KCA
def build_kca(T):
    t31, t32, t35 = T[D.kca_pe], T[D.kca_sched], T[D.kca_items]
    n = ['원서접수·시험 세부 시간은 CQ-Net 공고 확인', '정기검정 필기: 전 종목 CBT 평일 시행(세부 시행일자는 홈페이지 별도 공지)']
    for ri, r in enumerate(t31[1:], 1):
        rn = int(re.search(r'\d+', r[0]).group())
        add_schedule(f'KCA-PE-{rn}', 'KCA', 'regular', 'KCA-기술사', f'제{rn}회',
                     [phase_obj('written', r[1], r[2], r[3], f'상세:{D.kca_pe}:r{ri}', docs=r[4]),
                      phase_obj('interview', r[5], r[6], r[7], f'상세:{D.kca_pe}:r{ri}')], f'상세:{D.kca_pe}:r{ri}', n, round_no=rn)

    def mk(ri, sid, rl, rn, typ=None, label=None):
        r = t32[ri]
        written = None if '면제자' in r[1] or '이수자' in r[1] else phase_obj('written', r[1], r[2], r[3], f'상세:{D.kca_sched}:r{ri}', docs=r[4])
        ph = [x for x in (written, phase_obj('practical', r[5], r[6], r[7], f'상세:{D.kca_sched}:r{ri}')) if x]
        notes = list(n) + [f'적용 대상(원문 비고): {clean(r[8])}']
        if typ == 'school_exempt':
            notes.append('산업수요 맞춤형 및 특성화 고등학교 필기시험 면제자 검정 (일반인 필기시험 면제자 제외)')
        if typ == 'training_exempt':
            notes.append('기술훈련과정의 70/100 이상 이수자 검정 (일반인 필기시험 면제자 제외)')
        add_schedule(sid, 'KCA', typ or 'regular', 'KCA-' + (label or '기사·산업기사·기능사'), rl, ph, f'상세:{D.kca_sched}:r{ri}', notes, round_no=rn)
    mk(1, 'KCA-1-RADIO', '제1회', 1, label='전파전자통신 분야')
    mk(2, 'KCA-1-GEN', '제1회', 1, label='통신설비기능장·정보보안·정보통신·무선설비·방송통신 분야')
    mk(3, 'KCA-2-RADIO', '제2회', 2, label='전파전자통신기능사')
    mk(4, 'KCA-2-GEN', '제2회', 2, label='정보보안·정보통신·무선설비 분야')
    mk(5, 'KCA-3-SCHOOL', '제3회', 3, 'school_exempt', label='기능사 필기시험 면제자 검정')
    mk(6, 'KCA-4-RADIO', '제4회', 4, label='전파전자통신 기사·기능사')
    mk(7, 'KCA-4-GEN', '제4회', 4, label='통신설비기능장·정보보안·정보통신·무선설비·방송통신 분야')
    mk(8, 'KCA-4-TRAIN', '제4회', 4, 'training_exempt', label='기술훈련과정 이수자 검정')
    r = T[D.kca_occ_sched][1]
    add_schedule('KCA-OCC-1', 'KCA', 'occasional', 'KCA-수시', '수시 제1회',
                 [phase_obj('written', r[1], r[2], r[3], f'상세:{D.kca_occ_sched}:r1'), phase_obj('practical', r[4], r[5], r[6], f'상세:{D.kca_occ_sched}:r1')],
                 f'상세:{D.kca_occ_sched}', ['해외취업 및 국제항해 선박 승선 등 특수 목적의 수시검정 (교육기관 요청 등 대상 조건 있음)',
                               '필기(CBT): 서울, 부산 / 실기: 부산'], round_no=1)
    grade_of = {'기사': '기사', '산업기사': '산업기사', '기능사': '기능사'}
    for ri, r in enumerate(t35[2:], 2):
        a, b = clean(r[0]), clean(r[1])
        if a == b:
            name = a; grade = '기술사' if a.endswith('기술사') else '기능장'
        else:
            name = a + b; grade = grade_of[b]
        rounds = rounds_of(r[6])
        q = add_qual(name, grade, 'KCA', f'상세:{D.kca_items}:r{ri}', source_row=[r[0], r[1], r[6]])
        ref = f'상세:{D.kca_items}:r{ri} 시행회차 {clean(r[6])}'
        radio = a == '전파전자통신'
        for x in rounds:
            if grade == '기술사':
                add_map(q, f'KCA-PE-{x}', ref); continue
            if x == 1:
                add_map(q, 'KCA-1-RADIO' if radio else 'KCA-1-GEN', ref)
            elif x == 2:
                if radio and grade != '기능사':
                    rv('kca_round', ref, f'{name}: 제2회 매핑 대상 행 없음', 'error'); continue
                add_map(q, 'KCA-2-RADIO' if radio else 'KCA-2-GEN', ref)
            elif x == 3:
                add_map(q, 'KCA-3-SCHOOL', ref)
            elif x == 4:
                add_map(q, 'KCA-4-RADIO' if radio else 'KCA-4-GEN', ref)
        if grade == '기능사':
            add_map(q, 'KCA-4-TRAIN', f'상세:{D.kca_sched}:r8 (기능사 전종목)',
                    eligibility_note='기술훈련과정 70/100 이상 이수자만 응시 가능한 별도 검정입니다.')
            if name == '전파전자통신기능사':
                add_map(q, 'KCA-OCC-1', f'상세:{D.kca_occ_info}-{D.kca_occ_sched.split("t")[1]}', eligibility_note='수시검정은 해외취업·선박승선 등 특수 목적 대상자에 한해 시행됩니다.')
            if 3 not in rounds:
                if '3회는 신청 학교에서 시행' in (r[5] or ''):
                    rv('source_conflict', ref,
                       f'{name}: 시행회차는 "{clean(r[6])}"이나 같은 행 실기 시행지역에 "3회는 신청 학교에서 시행", {D.kca_sched} 제3회 비고 "기능사 전종목". 종목별·계획인원표({D.kca_plan}) 시행횟수 1회와도 대조 필요. 서비스에는 제3회 미노출(시행회차 기준), 안내문 표시.', 'error')
                    quals[q]['data_notice'] = '시행계획서 표 사이에 직업계고 필기시험 면제자 검정(제3회) 시행 여부가 다르게 기재되어 있습니다. 응시 전 한국방송통신전파진흥원(CQ-Net)에 확인하세요.'
    # 2회 (기능사 제외) 해석 검토 기록
    rv('interpretation', f'상세:{D.kca_sched}:r4,r7',
       f'"(기능사 제외)"는 마지막 분야(제2회 무선설비, 제4회 방송통신)에만 적용되는 것으로 해석. 근거: {D.kca_items} 시행회차(정보통신기능사 1·2·3·4회, 무선설비기능사 1·3·4회, 방송통신기능사 1회)와 {D.kca_plan} 시행횟수 일치.', 'info')


# ================================================================= changes
def build_changes(T, S):
    by_name = {v['name']: k for k, v in quals.items()}
    for r in T[D.biennial_odd][1:]:
        for n in re.split(r'[,，]\s*', r[1]):
            n = clean(n)
            m = re.match(r'^(.*?)(기능사)\((.*)\)$', n)
            if m: n = f'{m.group(1)}기능사({m.group(3)})'
            k = by_name.get(n) or by_name.get(n.replace('염색기능사(날염)', '염색기능사(날염)'))
            if not k:
                rv('name_lookup', f'상세:{D.biennial_odd}', f'홀수연도 시행 종목 {n} 매칭 실패', 'error'); continue
            changes.append(dict(qualification_id=k, year=YEAR, annual_status='scheduled', change_type='biennial_odd_year',
                                reason='검정시행 조정제도: 2027년 정상 시행 후 2028년부터 짝수 연도 미시행(홀수 연도에만 시행)',
                                source_reference=f'상세:별첨3 {D.biennial_odd}'))
    for r in T[D.biennial_skip][1:]:
        for n in re.split(r'[,，]\s*', r[1]):
            n = clean(n); k = by_name.get(n)
            if not k:
                rv('name_lookup', f'상세:{D.biennial_skip}', f'홀수연도 미시행 종목 {n} 매칭 실패', 'error'); continue
            changes.append(dict(qualification_id=k, year=YEAR, annual_status=quals[k]['annual_status'], change_type='biennial_not_held',
                                reason='검정시행 조정제도: 2027년부터 홀수 연도 미시행, 짝수 연도에만 시행 예정',
                                source_reference=f'상세:별첨3 {D.biennial_skip}; 요약:{SM.biennial}'))
    k = by_name['전자상거래관리사 1급']
    changes.append(dict(qualification_id=k, year=YEAR, annual_status='biennial_not_held', change_type='biennial_not_held',
                        reason='검정시행 조정제도(격년시행제도) 대상, 2027년 필기·실기 미시행', source_reference=f'상세:대한상공회의소 본문; 요약:{SM.biennial}'))
    for n in ('판금제관산업기사', '판금제관기능사'):
        changes.append(dict(qualification_id=by_name[n], year=YEAR, annual_status='scheduled', change_type='discontinuation_planned',
                            reason="2027년 시행, 2028년 미시행, 2029년 시행 후 2030년부터 검정중단", source_reference=f'상세:별첨3 {D.suspend}'))
    for r in S[SM.round_count][2:]:
        changes.append(dict(qualification_id=by_name[clean(r[1])], year=YEAR, annual_status='scheduled', change_type='round_count_changed',
                            reason=f"시행 회차 변경: 2026년 {r[2]}회 → 2027년 {r[3]}회 ({r[5]})", source_reference=f'상세:{SM.round_count}; 요약:{SM.round_count}'))
    for r in S[SM.round_change][1:]:
        n = clean(r[1]) ; k = by_name.get(n)
        if not k:
            rv('name_lookup', f'상세:{SM.round_change}', f'시행회차 변경 종목 {n} 매칭 실패', 'error'); continue
        changes.append(dict(qualification_id=k, year=YEAR, annual_status='scheduled', change_type='round_changed',
                            reason=f"시행 회차 변경: 2026년 {r[2]}회 → 2027년 {r[3]}회 ({r[4]})", source_reference=f'상세:{SM.round_change}; 요약:{SM.round_change}'))
    k = by_name['타워크레인설치해체기능사']
    changes.append(dict(qualification_id=k, year=YEAR, annual_status='not_conducted', change_type='not_conducted',
                        reason='기관 내부사정으로 검정형 미실시', source_reference=f'요약:{SM.agencies} 각주'))


# ================================================================= 검증용 집계
def summary_checks(S):
    expect = {}
    for r in S[SM.agencies][1:]:
        expect[r[1].strip()] = int(re.match(r'\d+', r[2]).group())
    ag = {a['name']: a['agency_id'] for a in AGENCIES}
    cnt = collections.Counter(q['agency_id'] for q in quals.values() if q['annual_status'] not in ('abolished', 'not_conducted'))
    out = []
    for name, n in expect.items():
        got = cnt[ag[name]]
        out.append(dict(agency=name, expected=n, actual=got, ok=n == got))
    hrdk = collections.Counter(q['grade'] for q in quals.values() if q['agency_id'] == 'HRDK' and q['annual_status'] != 'abolished')
    for r in S[SM.hrdk_counts][2:]:
        g, n = re.match(r'(\S+)\((\d+)\)', r[0]).groups()
        out.append(dict(agency='한국산업인력공단 ' + g, expected=int(n), actual=hrdk[g], ok=int(n) == hrdk[g]))
    return out


ALIASES = {
    '정보처리기사': ['정처기'], '정보처리산업기사': ['정처산기'], '정보처리기능사': ['정처기능사'],
    '산업안전기사': ['산안기'], '산업안전산업기사': ['산안산기'], '전기기사': ['전기기사'],
    '굴착기운전기능사': ['굴삭기', '포크레인', '포클레인'], '지게차운전기능사': ['지게차'],
    '미용사(일반)': ['미용사', '헤어'], '미용사(피부)': ['피부미용'], '미용사(네일)': ['네일'], '미용사(메이크업)': ['메이크업'],
    '한식조리기능사': ['한식', '조리사'], '양식조리기능사': ['양식'], '중식조리기능사': ['중식'], '일식조리기능사': ['일식'],
    '제과기능사': ['제과'], '제빵기능사': ['제빵'], '전산응용기계제도기능사': ['기계제도'], '전산응용건축제도기능사': ['건축제도'],
    '컴퓨터응용선반기능사': ['선반'], '컴퓨터응용밀링기능사': ['밀링'], '피복아크용접기능사': ['용접'],
    '웹디자인개발기능사': ['웹디자인기능사', '웹디'], '빅데이터분석기사': ['빅분기'], '사회조사분석사2급': ['사조사'],
    '직업상담사2급': ['직상'], '소방설비기사(기계분야)': ['소방기계'], '소방설비기사(전기분야)': ['소방전기'],
    '정보보안기사': ['정보보안'], '전자캐드기능사': ['전자캐드'], '3D프린터운용기능사': ['3D프린터'],
}


def main():
    detail, summary, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    T, d_tables = tables_by_id(detail); S, s_tables = tables_by_id(summary)
    D.__dict__.update(table_specs.resolve(d_tables, table_specs.DETAIL, '상세'))
    SM.__dict__.update(table_specs.resolve(s_tables, table_specs.SUMMARY, '요약'))
    D.pilda_days = [(tid, pilda_day(d_tables, tid)) for tid in D.hrdk_pilda]
    build_hrdk(T, S); build_others(T); build_kca(T); build_changes(T, S)
    for q in quals.values():
        for a in ALIASES.get(q['name'], []):
            if a not in q['aliases'] and a != q['name']: q['aliases'].append(a)
    counts = summary_checks(S)
    for c in counts:
        if not c['ok']:
            rv('count', f'요약:{SM.agencies}/{SM.hrdk_counts}', f"{c['agency']}: 기대 {c['expected']} / 실제 {c['actual']}", 'error')
    # 등급별 정기검정 회차가 하나도 없으면 표를 잘못 읽은 것이다.
    for g in ('HRDK-기술사', 'HRDK-기능장', 'HRDK-기사·산업기사·서비스', 'HRDK-기능사'):
        if not any(x['schedule_group'] == g and x['exam_type'] == 'regular' for x in schedules.values()):
            rv('count', g, f'{g}: 정기검정 회차 0건', 'error')
    strict = [r for r in review if r['severity'] == 'error' and r['kind'] in STRICT_KINDS]
    if strict:
        for r in strict: print('ERROR', r['kind'], r['source_reference'], r['detail'], file=sys.stderr)
        raise SystemExit(f'빌드 중단: 종목 수·회차·종목명 검사에서 {len(strict)}건 불일치. 공고 양식 변경 여부를 확인하세요.')
    # 연도 상태와 exam_types 정리
    for q in quals.values():
        if q['annual_status'] in ('biennial_not_held', 'abolished', 'not_conducted') and any(m['qualification_id'] == q['qualification_id'] for m in mappings):
            rv('inactive_mapping', q['source_reference'], f"{q['name']}: 미시행 상태인데 활성 매핑 존재", 'error')
    data_dir = out / 'data' / str(YEAR); data_dir.mkdir(parents=True, exist_ok=True)
    ql = sorted(quals.values(), key=lambda q: (GRADES[q['grade']][1], q['name']))
    sl = list(schedules.values())
    payload = dict(qualifications=ql, schedules=sl, mappings=mappings, agencies=AGENCIES, changes=changes)
    for k, v in payload.items():
        (data_dir / f'{k}.json').write_text(json.dumps(v, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    csv_dir = out / 'csv'; csv_dir.mkdir(parents=True, exist_ok=True)
    for k, v in payload.items():
        keys = list(dict.fromkeys(kk for x in v for kk in x))
        with (csv_dir / f'{k}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, keys); w.writeheader()
            for x in v:
                w.writerow({kk: json.dumps(vv, ensure_ascii=False) if isinstance(vv, (list, dict)) else ('' if vv is None else vv) for kk, vv in x.items()})
    rdir = out / 'review'; rdir.mkdir(parents=True, exist_ok=True)
    (rdir / 'review_items.json').write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding='utf-8')
    (rdir / 'count_checks.json').write_text(json.dumps(counts, ensure_ascii=False, indent=1), encoding='utf-8')
    print('qualifications', len(ql), 'schedules', len(sl), 'mappings', len(mappings), 'changes', len(changes), 'review', len(review))
    print(collections.Counter(q['annual_status'] for q in ql))
    for c in counts: print(('OK ' if c['ok'] else 'NG ') + json.dumps(c, ensure_ascii=False))
    for r in review: print(r['severity'], r['kind'], r['detail'][:160])


if __name__ == '__main__':
    main()
