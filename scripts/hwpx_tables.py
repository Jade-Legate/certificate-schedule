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
    return tables, paragraphs

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    t, p = extract(src)
    json.dump({'tables': t, 'paragraphs': p}, open(out, 'w'), ensure_ascii=False, indent=1)
    print(len(t), 'tables', len(p), 'paragraphs')
