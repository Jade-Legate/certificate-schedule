// 운영 설정값. 확정되지 않은 값은 빈 문자열로 두면 관련 UI·연동이 비활성화된다.
export const CONFIG = {
  // 배포 주소 (canonical·공유 링크 기준). 끝에 / 포함.
  siteUrl: 'https://jade-legate.github.io/certificate-schedule/',

  // 기본 연도 (data/metadata.json 의 current_year 가 우선)
  defaultYear: 2027,

  // 데뷔 로드맵 URL (담당자 제공값, 2026-11-24). 비우면 CTA 영역 미노출
  roadmapUrl: 'https://debut.ai.kr/?utm_source=naver_blog&utm_medium=referral&utm_campaign=blog&utm_content=post_18',

  // 오류 신고·문의처 (이메일 또는 URL). 비어 있으면 푸터에 표시하지 않는다 — 담당자 확인 필요
  contact: '',

  // 원문 출처
  // 고용노동부 공고 제2026-518호 원문(첨부 4종). 2026-11-25 브라우저로 직접 열어 제목·공고번호·첨부 확인
  sourceNoticeUrl: 'https://www.moel.go.kr/news/notice/noticeView.do?bbs_seq=20261100752',
  sourceCopyrightUrl: 'https://www.moel.go.kr/site/copyright/copyrightList.do',

  // GA4 측정 ID (예: 'G-XXXXXXXXXX') — 비어 있으면 분석 스크립트를 로드하지 않는다
  ga4MeasurementId: '',

  // 검색 이벤트 전송 지연(ms): 입력이 멈춘 뒤 한 번만 전송
  searchEventDelay: 900
};
