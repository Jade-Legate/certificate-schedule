"""공고 HWPX 표를 '문서 안 순서'가 아니라 '내용'으로 찾는다.

각 표는 세 가지로 식별한다.
  agency   : 표 앞에 나온 기관명 제목 (예: 한국산업인력공단). None이면 따지지 않음
  header   : 표 첫 두 행에 들어 있어야 하는 글자 (공백 제거 후 비교)
  heading  : 가까운 소제목(□, 1), 가. 등)에 들어 있어야 하는 정규식. window개 소제목 안에서 찾음
  context  : 바로 앞 본문 문단(○ 등 포함)에 들어 있어야 하는 정규식. window개 문단 안에서 찾음
  count    : 찾아야 하는 표 개수. 정수면 정확히 그 개수, 'many'면 1개 이상(페이지가 나뉘어 이어지는 표)

조건에 맞는 표가 기대 개수와 다르면 빌드를 멈춘다. 공고 양식이 바뀌면 여기만 고치면 된다.
"""
import re

HRDK, KCCI, KINS, KOFIC, KOCCA, KCA, KOMIR, KDATA, KIDP = (
    '한국산업인력공단', '대한상공회의소', '한국원자력안전기술원', '영화진흥위원회', '한국콘텐츠진흥원',
    '한국방송통신전파진흥원', '한국광해광업공단', '한국데이터산업진흥원', '한국디자인진흥원')


def spec(agency=None, header=(), heading=(), context=(), window=1, count=1):
    return dict(agency=agency, header=header, heading=heading, context=context, window=window, count=count)


# 상세(검정시행계획 본문) 표
DETAIL = {
    # 한국산업인력공단: 등급별 회차 일정
    'hrdk_pe_sched': spec(HRDK, ('회별', '면접시험'), (r'^\d+\)\s*기술사',)),
    'hrdk_ma_sched': spec(HRDK, ('회별', '실기시험'), (r'^\d+\)\s*기능장',)),
    'hrdk_en_sched': spec(HRDK, ('회별', '실기시험'), (r'^\d+\)\s*기사',)),
    'hrdk_cr_sched': spec(HRDK, ('회별', '실기시험'), (r'^\d+\)\s*기능사',)),
    'hrdk_summary': spec(HRDK, ('검정시행계획인원',), (r'시행계획 요약',)),
    # 한국산업인력공단: 종목별 시행회 (기사·기능사 표는 여러 쪽에 이어짐)
    'hrdk_pe_items': spec(HRDK, ('종목명', '시행회'), (r'^□\s*기술사 종목별',)),
    'hrdk_ma_items': spec(HRDK, ('종목명', '시행회'), (r'^□\s*기능장 종목별',)),
    'hrdk_en_items': spec(HRDK, ('직무분야', '종목명', '시행회'), (r'^□\s*기사·산업기사',), count='many'),
    'hrdk_cr_items': spec(HRDK, ('종목명', '구분', '면제검정'), (r'^□\s*기능사 종목별',), count='many'),
    # 기사 제3회 필답형 실기 날짜별 종목 (소제목에 날짜가 있음)
    'hrdk_pilda': spec(HRDK, ('연번', '등급', '부구분', '종목명'), (r'^□.*시행 종목',), count='many'),
    # 별첨3 격년 시행·검정중단
    'biennial_odd': spec(None, ('등급', '종목명'), (r'홀수 연도 시행 적용',)),
    'biennial_skip': spec(None, ('등급', '종목명'), (r'홀수 연도 미시행 적용',)),
    'suspend': spec(None, (), (r'검정중단 종목',)),
    # 대한상공회의소
    'kcci_sched': spec(KCCI, ('종목', '회별', '검정방법', '원서접수'), (r'정기검정 시행계획',), window=3),
    'kcci_roll': spec(KCCI, ('종목', '회별', '검정방법', '원서접수'), (r'상시검정',)),
    # 한국원자력안전기술원
    'kins_pe': spec(KINS, ('종목', '구분', '원서접수'), (r'기술사',)),
    'kins_en': spec(KINS, ('종목', '구분', '원서접수'), (r'기사\(',)),
    # 영화진흥위원회 (소제목이 같아 바로 앞 문단으로 구분)
    'kofic_in': spec(KOFIC, ('회별', '필기시험원서접수'), context=(r'영사산업기사',)),
    'kofic_cr': spec(KOFIC, ('회별', '필기시험원서접수'), context=(r'영사기능사',)),
    # 한국콘텐츠진흥원
    'kocca': spec(KOCCA, ('회별', '실기원서접수'), (r'시행일정',)),
    # 한국방송통신전파진흥원
    'kca_plan': spec(KCA, ('시행횟수',), context=(r'시행 횟수 및 계획인원',)),
    'kca_pe': spec(KCA, ('회별', '면접시험'), (r'^\d+\)\s*기술사',)),
    'kca_sched': spec(KCA, ('회별', '실기시험'), (r'기능장·기사',)),
    'kca_items': spec(KCA, ('시행회차',), (r'종목\(유형\)별 시행지역',)),
    'kca_occ_info': spec(KCA, ('종목', '횟수'), context=(r'시행종목 및 내역',)),
    'kca_occ_sched': spec(KCA, ('회별', '실기시험'), context=(r'○\s*시행일정',)),
    # 한국광해광업공단 · 한국데이터산업진흥원 · 한국디자인진흥원
    'komir': spec(KOMIR, ('종목명', '필기시험원서접수'), (r'시행일정',)),
    'kdata': spec(KDATA, ('회차', '필기시험원서접수'), (r'시행일정',)),
    'kidp': spec(KIDP, ('회차', '필기시험원서접수'), (r'시행일정',)),
}

# 요약 문서 표
SUMMARY = {
    'agencies': spec(None, ('검정위탁기관', '종목수')),
    'abolished': spec(None, ('구분', '종목명', '소관부처')),
    'biennial': spec(None, ('종목명', '검정위탁기관', '시행여부')),
    'hrdk_counts': spec(HRDK, ('시행종목', '정기검정시행횟수')),
    'round_count': spec(HRDK, ('종목명', '시행횟수', '증감')),
    'round_change': spec(HRDK, ('등급', '종목명'), context=(r'시행회차 변경',)),
}


def _compact(rows):
    return re.sub(r'\s+', '', ''.join(c or '' for r in rows[:2] for c in r))


def _match(t, s):
    if s['agency'] and t.get('agency') != s['agency']:
        return False
    head = _compact(t['rows'])
    if any(k not in head for k in s['header']):
        return False
    hd = t.get('headings', [])[-s['window']:]
    if any(not any(re.search(p, h) for h in hd) for p in s['heading']):
        return False
    cx = t.get('context', [])[-s['window']:]
    if any(not any(re.search(p, c) for c in cx) for p in s['context']):
        return False
    return True


class TableNotFound(SystemExit):
    pass


def resolve(tables, specs, label):
    """{이름: 표ID} 또는 {이름: [표ID, ...]} (count='many'). 기대 개수와 다르면 빌드 중단."""
    out, errors = {}, []
    for name, s in specs.items():
        hits = [t['table_id'] for t in tables if _match(t, s)]
        if s['count'] == 'many':
            ok = len(hits) >= 1
        else:
            ok = len(hits) == s['count']
        if not ok:
            errors.append(f'  [{label}] {name}: 기대 {s["count"]}개, 실제 {len(hits)}개 {hits} '
                          f'(agency={s["agency"]}, header={s["header"]}, heading={s["heading"]}, context={s["context"]})')
            continue
        out[name] = hits if s['count'] == 'many' else hits[0]
    if errors:
        raise TableNotFound('공고 표를 찾지 못했습니다. 공고 양식이 바뀌었는지 확인하고 scripts/table_specs.py 를 고치세요.\n'
                            + '\n'.join(errors))
    return out


def heading_of(tables, table_id):
    t = next(t for t in tables if t['table_id'] == table_id)
    return (t.get('headings') or [''])[-1]
