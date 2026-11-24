// 운영 설정값. 확정되지 않은 값은 빈 문자열로 두면 관련 UI·연동이 비활성화된다.
export const CONFIG = {
  // 배포 주소 (canonical·공유 링크 기준). 끝에 / 포함.
  siteUrl: 'https://jade-legate.github.io/certificate-schedule/',

  // 기본 연도 (data/metadata.json 의 current_year 가 우선)
  defaultYear: 2027,

  // 데뷔 로드맵 URL — 담당자 확인 전까지 비워 둔다(비어 있으면 CTA 버튼 미노출)
  roadmapUrl: '',

  // GA4 측정 ID (예: 'G-XXXXXXXXXX') — 비어 있으면 분석 스크립트를 로드하지 않는다
  ga4MeasurementId: '',

  // 검색 이벤트 전송 지연(ms): 입력이 멈춘 뒤 한 번만 전송
  searchEventDelay: 900,

  // 추천 검색어
  suggestions: ['전기기능사', '지게차', '컴활', '정보처리기사', '미용사', '한식조리'],
};
