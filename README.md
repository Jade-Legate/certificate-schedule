# 2027 국가기술자격 시험일정 검색기 · 데뷔(DEBUT)

자격증 이름을 검색하면 2027년 국가기술자격 종목의 시행 회차, 필기·실기·면접 원서접수 기간, 시험일, 합격자 발표일을 한 화면에서 보여 주는 정적 웹 서비스입니다.

- 배포: https://jade-legate.github.io/certificate-schedule/
- 원본 자료: 고용노동부 공고 제2026-518호 「2027년도 국가기술자격 검정시행계획」(2026. 11. 20., 관계부처 합동)
- 수록 범위: 541종목. 공식 집계 538종목에 폐지 2종목(포장산업기사, 석공예기능사)과 검정형 미실시 1종목(타워크레인설치해체기능사)을 더했습니다. 일정 46건, 종목별 매핑 1,169건입니다. 국방부 검정은 제외했습니다.
- 스택: HTML · CSS · Vanilla JS(ES Modules) · JSON / Python(데이터 추출·검증) / GitHub Pages. 서버, DB, 외부 API는 쓰지 않습니다.

## 구조

```text
docs/                    # GitHub Pages 배포 폴더
  index.html  css/style.css
  js/app.js              # UI·URL 상태·상호작용
  js/search.js           # 검색 정규화·순위(완전일치 > 앞부분 > 부분 > 별칭)
  js/schedule.js         # KST 날짜 계산·접수 상태·복사 텍스트·ICS
  js/config.js           # 운영 설정값 (로드맵 URL, GA4 ID 등)
  js/analytics.js        # GA4 (ID가 없으면 비활성)
  assets/                # 로고·파비콘·OG 이미지·Pretendard(OFL, 자체 호스팅)
  data/metadata.json     # 연도별 데이터셋 정보
  data/2027/{qualifications,schedules,mappings,agencies,changes}.json
data/2027/csv/           # JSON과 같은 레코드의 CSV
data/2027/review/        # 검증 리포트, 검수 기록(REVIEW.md), 자동 검수 목록
scripts/                 # 추출·정규화·검증 파이프라인
tests/e2e.mjs            # Playwright E2E QA (결과: tests/results/)
source/                  # 원본 HWPX·PDF (gitignore, 공개 저장소에 올리지 않음)
```

## 데이터 모델

| 파일 | 설명 |
|---|---|
| `qualifications.json` | 종목 마스터. `qualification_id`(종목명 해시, 연도가 바뀌어도 유지), `name`, `grade`/`grade_code`, `agency_id`, `aliases`, `exam_types`, `annual_status`(scheduled · partially_held · biennial_not_held · abolished · not_conducted), `status_reason`, `has_written_exam`, `source_reference`, `source_row`(원문 행) |
| `schedules.json` | 시험일정. `exam_type`(regular · rolling · school_exempt · training_exempt · occasional), `schedule_group`, `round`, `phases[]` (`phase`, `registration_periods[]`, `exam_periods[]`, `result_dates[]`, `excluded_dates[]`, `document_submission`, `raw` 원문, `correction`), `publication_status`, `notes` |
| `mappings.json` | 종목별 일정 매핑. `eligibility_note`, `override`(예: 필기 없음, 종목별 필답형 시험일), `verification`, `source_reference` |
| `agencies.json` | 시행기관과 공식·접수 URL |
| `changes.json` | 연도별 변경사항(폐지, 격년 미시행, 회차 변경, 검정중단 예정 등) |

검정 유형, 연도별 시행 여부, 일정 공개 여부, 응시 자격 조건은 서로 다른 속성으로 관리합니다. 예를 들어 상시검정이라고 해서 일정 미공개와 같은 상태로 취급하지 않습니다.

## 로컬 실행

```bash
mkdir -p .site && ln -sfn ../docs .site/certificate-schedule   # Pages 하위 경로 재현
python3 -m http.server 8765 --directory .site
# http://localhost:8765/certificate-schedule/
# 날짜 상태 확인용: ?today=2027-03-18 (KST 기준 오늘 대신 지정한 날짜 사용)
```

E2E QA는 Playwright가 필요합니다(`npm i`). `BASE=http://localhost:8765/certificate-schedule/ node tests/e2e.mjs qa-shots`로 실행합니다. 배포 환경은 `BASE=https://jade-legate.github.io/certificate-schedule/`로 지정합니다.

## 운영 설정 (`docs/js/config.js`)

| 키 | 설명 | 현재 |
|---|---|---|
| `roadmapUrl` | 데뷔 로드맵 CTA 링크. 비어 있으면 CTA 영역을 숨깁니다 | `https://debut.ai.kr/?utm_source=naver_blog&utm_medium=referral&utm_campaign=blog&utm_content=post_18` (담당자 제공) |
| `ga4MeasurementId` | GA4 측정 ID(`G-…`). 비어 있으면 분석 스크립트를 로드하지 않습니다 | 미설정 |
| `siteUrl` | 공유 링크와 canonical 기준 주소 | 배포 주소 |
| `suggestions` | 추천 검색어 | |

GA4 이벤트: `page_view`(자동), `certificate_search`(입력이 멈춘 뒤 1회, 결과 건수와 검색어 길이만 전송), `search_no_result`, `certificate_select`, `schedule_view`, `official_site_click`, `roadmap_cta_click`, `share_click`(method: copy · native · copy_schedule · ics). 검색어 원문과 개인정보는 전송하지 않습니다.

URL 파라미터는 `?year=2027`, `&q=전기기능사`, `&grade=craft|industrial|engineer|master|pe|service`, `&qualification=<ID>`를 지원합니다. `utm_*` 파라미터는 화면 상태가 바뀌어도 유지됩니다.

## 네이버 블로그 삽입 링크

```text
https://jade-legate.github.io/certificate-schedule/?year=2027&utm_source=naver_blog&utm_medium=referral&utm_campaign=2027_certificate_schedule&utm_content=schedule_table_bottom
```

삽입 위치마다 `utm_content` 값만 바꿔 사용합니다(예: `intro_banner`, `schedule_table_bottom`, `post_footer`). 특정 종목 글에서는 `&qualification=<ID>`를 붙이면 해당 종목 상세가 바로 열립니다. ID는 검색기에서 종목을 연 뒤 ‘링크 공유’로 복사할 수 있습니다.

## 연도별 데이터 업데이트 방법 (예: 2028년)

1. 고용노동부 공고의 상세본·요약본 HWPX와 PDF를 `source/2028_detail.hwpx`, `source/2028_summary.hwpx`, `source/2028_detail.pdf`, `source/2028_summary.pdf`로 저장합니다.
2. 표 구조를 확인합니다: `python3 -I scripts/hwpx_dump.py source/2028_detail.hwpx > build/order.txt`, `python3 -I scripts/print_tables.py build/out/...`
   표 번호(`s0t7` 등)와 열 순서가 바뀌었으면 `scripts/build_data.py`의 기관별 빌드 함수를 수정합니다. `YEAR`, `OVERRIDES`(확정 수정), 공고번호와 발표일(`export_metadata.py`)도 갱신합니다.
3. `scripts/build_all.sh 2028 <갱신일>`을 실행합니다. HWPX 추출, JSON·CSV 생성, PDF 대조 검증, metadata 갱신까지 한 번에 진행됩니다.
4. `data/2028/review/validation_report.md`가 전 항목 통과인지 확인하고, `review_items.json`의 `error`·`info` 항목을 검토해 `REVIEW.md`에 결정을 기록합니다. 기관별 종목 수의 기대값도 요약본에 맞게 고칩니다(`validate.py`의 `expect`).
5. `docs/js/config.js`의 `defaultYear`와 `index.html`의 제목·메타·OG 문구, `assets/og-image.png`(`scripts/make_assets.py`)를 새 연도로 바꿉니다.
6. 로컬에서 E2E QA를 실행한 뒤 커밋·푸시합니다. GitHub Pages는 main 브랜치의 `/docs`에서 자동 배포됩니다.

이전 연도 데이터는 `docs/data/<연도>/`에 그대로 두면 `?year=` 파라미터로 계속 조회할 수 있습니다.

## 시행 중 일정 정정 공고가 나온 경우

정정이 공식 공고로 확인되면 `build_data.py`의 `OVERRIDES`(또는 해당 기관 함수)에 원문 값, 정정 값, 사유, 근거 공고를 기록합니다. 그다음 `build_all.sh`를 다시 실행합니다. JSON을 직접 수정하지 않습니다. 직접 고치면 CSV와 JSON이 어긋나 검증에서 실패합니다.

## 원본 문서

원본 HWPX·PDF는 이용허락 범위가 명시되지 않아 저장소에 포함하지 않습니다(`source/`는 gitignore). 고용노동부 누리집과 큐넷의 공고에서 받을 수 있습니다.

## 라이선스와 브랜드

- Pretendard: SIL Open Font License 1.1 — 전문은 `docs/assets/fonts/LICENSE-Pretendard-OFL.txt` (폰트 파일과 함께 배포)
- 데뷔 로고: 담당자 승인(2026-11-24)을 받아 Figma 원본(`Logo` 컴포넌트)을 SVG로 내보내 `docs/assets/logo.svg`로 사용합니다. OG 이미지와 아이콘은 `scripts/make_assets.py`로 생성합니다.
