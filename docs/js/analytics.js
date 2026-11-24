// GA4 연동. 측정 ID가 없으면 아무 것도 전송하지 않는다.
// 개인정보 보호: 검색어 원문은 전송하지 않고 결과 건수·공식 종목 ID만 보낸다.
import { CONFIG } from './config.js';

let enabled = false;

export function initAnalytics() {
  const id = CONFIG.ga4MeasurementId;
  if (!id || !/^G-[A-Z0-9]+$/.test(id)) return;
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() { window.dataLayer.push(arguments); };
  window.gtag('js', new Date());
  // page_view 는 config 호출 시 자동 전송 (UTM 파라미터 포함)
  window.gtag('config', id, { anonymize_ip: true });
  enabled = true;
}

export function track(name, params = {}) {
  if (!enabled || typeof window.gtag !== 'function') return;
  try { window.gtag('event', name, params); } catch (_) { /* 분석 실패는 무시 */ }
}

// 입력 중 과도한 이벤트 방지: 입력이 멈춘 뒤 1회, 동일 조건 반복 전송 안 함
let timer = null; let lastKey = '';
export function trackSearch({ term, grade, count }) {
  clearTimeout(timer);
  if (!term) return;
  timer = setTimeout(() => {
    const key = `${term}|${grade}|${count}`;
    if (key === lastKey) return;
    lastKey = key;
    track('certificate_search', { grade_filter: grade || 'all', result_count: count, query_length: term.length });
    if (count === 0) track('search_no_result', { grade_filter: grade || 'all', query_length: term.length });
  }, CONFIG.searchEventDelay);
}
