"""공식 PDF에서 글리프 좌표 기준으로 텍스트를 줄 단위 추출(pdfplumber).
pdftotext 텍스트 레이어는 HWP 변환 PDF의 양쪽정렬 표에서 글자 순서가 뒤섞이므로 좌표 기반 추출을 함께 사용한다.
사용: python3 -I scripts/pdf_text.py <in.pdf> <out.txt>"""
import sys, pdfplumber
with pdfplumber.open(sys.argv[1]) as pdf, open(sys.argv[2], 'w', encoding='utf-8') as f:
    for i, p in enumerate(pdf.pages, 1):
        f.write(f'\n<<PAGE {i}>>\n')
        f.write((p.extract_text(x_tolerance=1.5, y_tolerance=3) or '') + '\n')
