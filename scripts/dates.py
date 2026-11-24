"""시행계획 원문 날짜 문자열 파서.

원문 예시
  "1. 5.(화)∼\n1. 8.(금)"           -> 기간
  "7 10.(토)∼\n7. 28.(수)"          -> 점 누락(7.10)
  "3. 15.(월)∼\n3. 19.(금)\n*3.18.(목) 제외" -> 기간 + 제외일
  "1차 4. 9.(금)\n2차 4. 16.(금)"   -> 복수 발표일
  "’27.3.8~12"                     -> 종료일이 일(day)만 있는 기간
  "03.04~03.10"                    -> 0 패딩
연도는 기본 2027, 원문에 ’26. 처럼 연도가 있으면 그 연도를 쓴다.
요일 표기가 있으면 실제 요일과 대조해 weekday_mismatch 로 보고한다.
"""
import re, datetime

WD = '월화수목금토일'
DATE_RE = re.compile(
    r"(?:[’'‘`](?P<yy>\d{2})\.\s*)?(?P<m>\d{1,2})(?:\.\s*|\s+)(?P<d>\d{1,2})\.?\s*(?:\((?P<w>[월화수목금토일])\))?")
RANGE_SEP = re.compile(r"\s*[∼~〜]\s*")


class ParseIssue(Exception):
    pass


def _mk(yy, m, d, w, default_year, issues, raw):
    year = 2000 + int(yy) if yy else default_year
    try:
        dt = datetime.date(year, int(m), int(d))
    except ValueError:
        issues.append(f'invalid_date:{raw!r}')
        return None
    if w and WD[dt.weekday()] != w:
        issues.append(f'weekday_mismatch:{dt.isoformat()} 원문({w}) 실제({WD[dt.weekday()]})')
    return dt


def parse_cell(text, default_year=2027):
    """원문 셀 -> dict(periods=[{start,end,label}], excluded=[...], issues=[...])"""
    issues, periods, excluded = [], [], []
    if not text:
        return dict(periods=[], excluded=[], issues=[])
    lines = [l.strip() for l in text.replace('\r', '').split('\n') if l.strip()]
    # 범위가 줄바꿈으로 나뉜 경우 결합: "1. 5.(화)∼" + "1. 8.(금)"
    merged = []
    for l in lines:
        if merged and (re.search(r"[∼~〜]\s*$", merged[-1]) or re.match(r"^[∼~〜]", l)):
            merged[-1] = merged[-1] + l
        else:
            merged.append(l)
    for l in merged:
        is_excl = '제외' in l and re.search(r"\d", l)
        label = None
        mlabel = re.match(r"^(\d차)\s*", l)
        if mlabel:
            label = mlabel.group(1); l = l[mlabel.end():]
        parts = RANGE_SEP.split(l, maxsplit=1)
        ms = list(DATE_RE.finditer(parts[0]))
        if not ms:
            if re.search(r"\d", l):
                issues.append(f'unparsed:{l!r}')
            continue
        a = ms[0]
        start = _mk(a['yy'], a['m'], a['d'], a['w'], default_year, issues, l)
        end = start
        if len(parts) == 2:
            mb = DATE_RE.search(parts[1])
            if mb:
                y2 = mb['yy'] or a['yy']
                end = _mk(y2, mb['m'], mb['d'], mb['w'], default_year, issues, l)
            else:
                dm = re.match(r"(\d{1,2})", parts[1])
                if dm and start:
                    end = _mk(a['yy'], a['m'], dm.group(1), None, default_year, issues, l)
                else:
                    issues.append(f'unparsed_range_end:{l!r}')
        if start and end and end < start:
            issues.append(f'reversed_range:{l!r}')
        if is_excl:
            excluded.append(start.isoformat())
            continue
        if start:
            p = {'start': start.isoformat(), 'end': (end or start).isoformat()}
            if label: p['label'] = label
            periods.append(p)
    return dict(periods=periods, excluded=excluded, issues=issues)


if __name__ == '__main__':
    tests = ["1. 5.(화)∼\n1. 8.(금)", "7 10.(토)∼\n7. 28.(수)", "3. 15.(월)∼\n3. 19.(금)\n*3.18.(목) 제외",
             "1차 4. 9.(금)\n2차 4. 16.(금)", "’27.3.8~12", "03.04~03.10", "’26.7.16", "1. 19.(화)∼1. 23.(토)",
             "1.25(월)\n~1.28(목)", "3.31.~4.9.", "5.29(토)", "9 21.(화)∼9. 25.(토)"]
    for t in tests:
        print(repr(t), '->', parse_cell(t))
