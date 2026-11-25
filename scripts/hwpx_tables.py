"""HWPX(OWPML) 문서에서 표와 본문 문단을 추출한다.
출력: [{table_id, section, index, rows:[[cell_text,...]], cells:[{r,c,rs,cs,text}]}]
"""
import sys, json, zipfile, re
import xml.etree.ElementTree as ET
NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'

def para_text(p):
    out = []
    for run in p.iter(HP + 'run'):
        for ch in run:
            if ch.tag == HP + 't':
                out.append(''.join(ch.itertext()))
            elif ch.tag == HP + 'tbl':
                pass
    return ''.join(out)

def cell_text(tc):
    paras = []
    sub = tc.find(HP + 'subList')
    if sub is None: return ''
    for p in sub.findall(HP + 'p'):
        t = para_text(p).strip()
        # nested tables inside cell
        for nt in p.iter(HP + 'tbl'):
            pass
        if t: paras.append(t)
    return '\n'.join(paras)

def extract(path):
    z = zipfile.ZipFile(path)
    secs = sorted(n for n in z.namelist() if re.match(r'Contents/section\d+\.xml', n))
    tables, paragraphs = [], []
    for si, sname in enumerate(secs):
        root = ET.fromstring(z.read(sname))
        ti = 0
        # walk top-level paragraphs in order, record text and tables
        for p in root.iter(HP + 'p'):
            t = para_text(p).strip()
            tbls = [x for x in p.iter(HP + 'tbl')]
            if t: paragraphs.append({'section': si, 'text': t})
        for tbl in root.iter(HP + 'tbl'):
            cells = []
            for tc in tbl.iter(HP + 'tc'):
                if tc.find('..') is not None: pass
                addr = tc.find(HP + 'cellAddr'); span = tc.find(HP + 'cellSpan')
                cells.append({'r': int(addr.get('rowAddr')), 'c': int(addr.get('colAddr')),
                              'rs': int(span.get('rowSpan')), 'cs': int(span.get('colSpan')),
                              'text': cell_text(tc)})
            # nested table cells are iterated too; keep only direct ones
            direct = []
            for tr in tbl.findall(HP + 'tr'):
                for tc in tr.findall(HP + 'tc'):
                    addr = tc.find(HP + 'cellAddr'); span = tc.find(HP + 'cellSpan')
                    direct.append({'r': int(addr.get('rowAddr')), 'c': int(addr.get('colAddr')),
                                   'rs': int(span.get('rowSpan')), 'cs': int(span.get('colSpan')),
                                   'text': cell_text(tc)})
            nr = int(tbl.get('rowCnt')); nc = int(tbl.get('colCnt'))
            grid = [[None]*nc for _ in range(nr)]
            for c in direct:
                for dr in range(c['rs']):
                    for dc in range(c['cs']):
                        if c['r']+dr < nr and c['c']+dc < nc:
                            grid[c['r']+dr][c['c']+dc] = c['text']
            tables.append({'table_id': f's{si}t{ti}', 'section': si, 'index': ti,
                           'rows': grid, 'cells': direct})
            ti += 1
        # 표 앞 문맥(본문 문단·소제목·기관명)을 표 순서대로 붙인다. 표 번호는 위와 같은 전위 순회 순서.
        for i, ctx in enumerate(_contexts(root)):
            tables[len(tables) - ti + i].update(ctx)
    return tables, paragraphs


HEADING = re.compile(r'^(□|<|[0-9]+[.)]|[가-하][.)]|\(?[0-9]+\)|[ⅠⅡⅢⅣⅤ])')
AGENCY = re.compile(r'^(?:[0-9]+\.\s*)?([가-힣]+(?:공단|상공회의소|기술원|위원회|진흥원))$')


def _contexts(root):
    """표마다 {context: 직전 본문 문단 6개, headings: 직전 소제목 8개, agency: 직전 기관명 제목}.
    표 안의 문단은 본문 문맥에서 제외한다."""
    out, paras, heads, buf = [], [], [], []
    agency = [None]

    def walk(n, in_tbl):
        if n.tag == HP + 'tbl':
            pending = ''.join(buf).strip()  # 표와 같은 문단에서 표 앞에 있는 글자
            ctx, hd = paras[-6:], heads[-8:]
            if pending:
                ctx = (ctx + [pending])[-6:]
                if HEADING.match(pending): hd = (hd + [pending])[-8:]
            out.append({'context': ctx, 'headings': hd, 'agency': agency[0]})
            for c in n: walk(c, True)
            return
        if n.tag == HP + 't' and not in_tbl:
            buf.append(''.join(n.itertext()))
        for c in n: walk(c, in_tbl)
        if n.tag == HP + 'p' and not in_tbl:
            t = ''.join(buf).strip(); buf.clear()
            if not t: return
            paras.append(t)
            if HEADING.match(t): heads.append(t)
            m = AGENCY.match(t)
            if m: agency[0] = m.group(1)

    walk(root, False)
    return out

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    t, p = extract(src)
    json.dump({'tables': t, 'paragraphs': p}, open(out, 'w'), ensure_ascii=False, indent=1)
    print(len(t), 'tables', len(p), 'paragraphs')
