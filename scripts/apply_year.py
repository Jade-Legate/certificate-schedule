"""정적 HTML·설정·OG 이미지의 연도를 docs/data/metadata.json 의 current_year 로 맞춘다.

검색엔진과 링크 미리보기(네이버 블로그·메신저)는 JS를 실행하지 않으므로 index.html 의 제목·설명·OG 문구는
정적 텍스트로 둬야 한다. 해마다 손으로 고치지 않도록 이 스크립트가 바꾼다. build_all.sh 마지막 단계에서 실행된다.

사용: python3 -I scripts/apply_year.py            (변경 내용 출력)
      python3 -I scripts/apply_year.py --check    (바꿀 곳이 있으면 실패, CI용)
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
meta = json.loads((DOCS / 'data' / 'metadata.json').read_text(encoding='utf-8'))
year = str(meta['current_year'])
check = '--check' in sys.argv

# 연도 뒤에 오는 말로 '서비스 연도'인 곳만 고른다 (다른 연도 숫자는 건드리지 않음)
YEAR_RE = re.compile(r'(?<!\d)20\d{2}(?=(년|\s*(자격증|국가기술자격)))')
targets = [
    (DOCS / 'index.html', lambda s: YEAR_RE.sub(year, s)),
    (DOCS / 'js' / 'config.js', lambda s: re.sub(r'(defaultYear:\s*)\d{4}', rf'\g<1>{year}', s)),
]
changed = []
for path, fn in targets:
    old = path.read_text(encoding='utf-8'); new = fn(old)
    if new != old:
        changed.append(path.relative_to(ROOT))
        if not check: path.write_text(new, encoding='utf-8')
if check:
    if changed:
        sys.exit(f'연도({year})와 다른 곳이 있습니다: ' + ', '.join(map(str, changed)) + ' → python3 -I scripts/apply_year.py 실행')
    print(f'OK: 정적 파일 연도 = {year}')
    sys.exit(0)
subprocess.run([sys.executable, '-I', str(ROOT / 'scripts' / 'make_assets.py'), str(DOCS / 'assets')], check=True)
print(f'연도 {year} 적용:', ', '.join(map(str, changed)) or '변경 없음', '+ OG 이미지 재생성')
