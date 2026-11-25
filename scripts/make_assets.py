"""브랜드 에셋 생성: 공식 로고(docs/assets/logo.svg, Figma 원본 export)로 OG 이미지·아이콘 생성.
사용: python3 -I scripts/make_assets.py docs/assets
OG 이미지의 연도·종목 수는 docs/data/metadata.json (current_year, counts.qualifications)에서 읽는다."""
import sys, pathlib, json
from PIL import Image, ImageDraw, ImageFont
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
META = json.loads((out.parent / 'data' / 'metadata.json').read_text(encoding='utf-8'))
YEAR = META['current_year']; N_QUAL = META['datasets'][str(YEAR)]['counts']['qualifications']
F = '/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc'
def font(w, size):
    # ttc index 1 = KR
    return ImageFont.truetype(F.format(w), size, index=1)
INK, PINK, GREY, BG = (18, 18, 18), (255, 18, 92), (77, 81, 89), (242, 243, 246)

# OG 1200x630
im = Image.new('RGB', (1200, 630), BG); d = ImageDraw.Draw(im)
d.rounded_rectangle((60, 60, 1140, 570), 28, fill=(255, 255, 255))
import subprocess, io
logo_png = subprocess.run(['rsvg-convert', '-h', '64', str(out / 'logo.svg')], capture_output=True, check=True).stdout
logo = Image.open(io.BytesIO(logo_png)).convert('RGBA'); im.paste(logo, (120, 118), logo)
d.text((120, 230), f'국가기술자격 {N_QUAL}종목', font=font('Bold', 40), fill=PINK)
d.text((120, 290), f'{YEAR} 자격증 시험일정', font=font('Black', 88), fill=INK)
d.text((120, 430), '자격증 이름만 검색하면 필기·실기 원서접수와 시험일을 한눈에', font=font('Medium', 32), fill=GREY)
d.rounded_rectangle((120, 492, 520, 500), 4, fill=PINK)
im.save(out / 'og-image.png', optimize=True)

def icon(size):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), int(size * .22), fill=INK)
    f = font('Black', int(size * .62)); t = 'd'
    bb = d.textbbox((0, 0), t, font=f); w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((size - w) / 2 - bb[0], (size - h) / 2 - bb[1] - size * .02), t, font=f, fill=(255, 255, 255))
    r = size * .08; cx, cy = size * .74, size * .26
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PINK)
    return im
icon(64).save(out / 'favicon.png'); icon(180).convert('RGB').save(out / 'apple-touch-icon.png')
if False: (out / 'logo.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="123" height="32" viewBox="0 0 123 32" role="img" aria-label="데뷔 DEBUT">
<text x="0" y="24" font-family="Pretendard, 'Apple SD Gothic Neo', sans-serif" font-size="24" font-weight="800" letter-spacing="-1" fill="#121212">début</text>
<text x="68" y="24" font-family="Pretendard, 'Apple SD Gothic Neo', sans-serif" font-size="19" font-weight="700" fill="#121212">데뷔</text></svg>
''', encoding='utf-8')
print('ok')
