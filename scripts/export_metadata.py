"""docs/data/metadata.json 생성 (연도별 데이터셋 목록, 출처, 갱신일, 검증 결과 요약).
사용: python3 -I scripts/export_metadata.py <year> <data_updated YYYY-MM-DD> <validation_report.md> <docs/data/metadata.json>"""
import sys, json, re, pathlib
year, updated, report, out = sys.argv[1:5]
d = pathlib.Path(out).parent / year
q = json.loads((d / 'qualifications.json').read_text()); s = json.loads((d / 'schedules.json').read_text()); m = json.loads((d / 'mappings.json').read_text())
rep = pathlib.Path(report).read_text()
passed = re.search(r'결과: (.*) \((\d+)/(\d+)\)', rep)
meta_path = pathlib.Path(out)
meta = json.loads(meta_path.read_text()) if meta_path.exists() else {'current_year': int(year), 'datasets': {}}
meta['current_year'] = max(int(year), meta.get('current_year', 0))
meta['datasets'][year] = {
    'year': int(year),
    'title': f'{year}년도 국가기술자격 검정시행계획',
    'announcement_no': '고용노동부 공고 제2026-518호',
    'published': '2026-11-20',   # 문서에 기재된 공고일
    'posted': '2026-11-23',      # 고용노동부 누리집 게시일
    'publisher': '고용노동부(관계부처 합동)',
    'source_documents': [f'{year}년 국가기술자격 검정시행계획(상세본, HWPX·PDF)', f'{year}년 국가기술자격 검정시행계획(요약본, HWPX·PDF)'],
    'data_updated': updated,
    'counts': {'qualifications': len(q), 'official_total': sum(1 for x in q if x['annual_status'] not in ('abolished', 'not_conducted')),
               'schedules': len(s), 'mappings': len(m)},
    'validation': {'summary': passed.group(1) if passed else None, 'passed': int(passed.group(2)) if passed else None, 'total': int(passed.group(3)) if passed else None},
    'scope_note': '국방부 시행 군 검정(67종목)은 일반인 응시 대상이 아니어서 제외했습니다.',
}
meta['years'] = sorted(int(k) for k in meta['datasets'])
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(meta['datasets'][year], ensure_ascii=False))
