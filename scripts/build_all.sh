#!/usr/bin/env bash
# 연도별 데이터 전체 빌드: HWPX 추출 → 정규화 JSON/CSV → PDF 대조 검증 → metadata
# 사용: scripts/build_all.sh 2027 2026-11-24
set -euo pipefail
YEAR=${1:-2027}; UPDATED=${2:-$(TZ=Asia/Seoul date +%F)}
ROOT=$(cd "$(dirname "$0")/.." && pwd); SRC="$ROOT/source"; TMP="$ROOT/build"
mkdir -p "$TMP"
python3 -I "$ROOT/scripts/build_data.py" "$SRC/${YEAR}_detail.hwpx" "$SRC/${YEAR}_summary.hwpx" "$TMP/out"
python3 -I "$ROOT/scripts/pdf_text.py" "$SRC/${YEAR}_detail.pdf" "$TMP/detail_pdf.txt"
python3 -I "$ROOT/scripts/pdf_text.py" "$SRC/${YEAR}_summary.pdf" "$TMP/summary_pdf.txt"
pdftotext -layout "$SRC/${YEAR}_summary.pdf" "$TMP/summary_pdf_layout.txt"
mkdir -p "$ROOT/docs/data/$YEAR" "$ROOT/data/$YEAR/csv" "$ROOT/data/$YEAR/review"
cp "$TMP"/out/data/$YEAR/*.json "$ROOT/docs/data/$YEAR/"
cp "$TMP"/out/csv/*.csv "$ROOT/data/$YEAR/csv/"
cp "$TMP"/out/review/*.json "$ROOT/data/$YEAR/review/"
python3 -I "$ROOT/scripts/validate.py" "$ROOT/docs/data/$YEAR" "$ROOT/data/$YEAR/csv" "$TMP/detail_pdf.txt" "$TMP/summary_pdf.txt" \
  "$ROOT/data/$YEAR/review/validation_report.md" "$TMP/summary_pdf_layout.txt"
python3 -I "$ROOT/scripts/export_metadata.py" "$YEAR" "$UPDATED" "$ROOT/data/$YEAR/review/validation_report.md" "$ROOT/docs/data/metadata.json"
python3 -I "$ROOT/scripts/apply_year.py"
