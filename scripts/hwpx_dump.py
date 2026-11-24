"""문서 순서대로 최상위 문단과 표를 텍스트로 덤프(검수·확인용)."""
import sys, zipfile, re, xml.etree.ElementTree as ET
HP='{http://www.hancom.co.kr/hwpml/2011/paragraph}'
def ptext(p):
    o=[]
    for run in p.findall(HP+'run'):
        for ch in run:
            if ch.tag==HP+'t': o.append(''.join(ch.itertext()))
    return ''.join(o)
z=zipfile.ZipFile(sys.argv[1]); secs=sorted(n for n in z.namelist() if re.match(r'Contents/section\d+\.xml',n))
for si,s in enumerate(secs):
    root=ET.fromstring(z.read(s)); ti=0
    # count tables in iter order to keep ids aligned with hwpx_tables (root.iter order)
    order={id(t):i for i,t in enumerate(root.iter(HP+'tbl'))}
    for p in root.findall(HP+'p'):
        t=ptext(p).strip()
        if t: print(f'[s{si}] {t}')
        for run in p.findall(HP+'run'):
            for tbl in run.findall(HP+'tbl'):
                tid=order[id(tbl)]
                print(f'<<TABLE s{si}t{tid} {tbl.get("rowCnt")}x{tbl.get("colCnt")}>>')
