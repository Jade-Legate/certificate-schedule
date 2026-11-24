// E2E QA — 사용: BASE=http://localhost:8765/certificate-schedule/ node tests/e2e.mjs [out_dir]
// 필수 테스트 케이스(기획서 12장) + 뷰포트 + URL 복원 + 뒤로 가기 + 키보드 + JSON 실패 + 콘솔 오류
import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = process.env.BASE || 'http://localhost:8765/certificate-schedule/';
const OUT = process.argv[2] || 'qa-shots';
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const consoleErrors = [];
const ok = (name, cond, detail = '') => { results.push({ name, ok: !!cond, detail }); console.log(`${cond ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`); };

const browser = await chromium.launch();
async function newPage(viewport = { width: 1280, height: 900 }, opts = {}) {
  const ctx = await browser.newContext({ viewport, locale: 'ko-KR', timezoneId: 'Asia/Seoul', ...opts });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${page.url()} :: ${m.text()}`); });
  page.on('requestfailed', (r) => consoleErrors.push(`${page.url()} :: requestfailed ${r.url()} ${r.failure()?.errorText}`));
  page.on('pageerror', (e) => consoleErrors.push(`${page.url()} :: pageerror ${e.message}`));
  return page;
}
const detailText = (p) => p.locator('#detail').innerText();
async function openQ(page, q, extra = '') {
  await page.goto(`${BASE}?year=2027&q=${encodeURIComponent(q)}${extra}`);
  await page.waitForSelector('#results .item, #empty:not([hidden])');
}
async function pick(page, name) {
  await page.locator('#results .item', { has: page.locator('.item__name', { hasText: new RegExp(`^${name.replace(/[()]/g, '\\$&')}$`) }) }).first().click();
  await page.waitForSelector('#detail-title');
}

const page = await newPage();

// 1 전기기능사 — 일반 정기검정
await openQ(page, '전기기능사');
let first = await page.locator('#results .item__name').first().innerText();
ok('검색 우선순위: 전기기능사 완전일치 1순위', first === '전기기능사', first);
await pick(page, '전기기능사');
let t = await detailText(page);
ok('전기기능사: 제1~4회 + 면제자 검정 탭', ['제1회', '제2회', '제3회', '제4회', '필기시험 면제자 검정'].every((x) => t.includes(x)));
ok('전기기능사: 필기/실기 접수·시험·발표 표시', ['필기 원서접수', '필기시험', '필기 합격자 발표', '실기 원서접수', '실기시험', '최종 합격자 발표'].every((x) => t.includes(x)));
ok('전기기능사: 가장 가까운 접수 강조(제1회 1.5~1.8)', t.includes('가장 가까운 원서접수') && t.includes('2027. 1. 5.(화) ~ 2027. 1. 8.(금)'));
ok('전기기능사: 응시자격 제한 없음 안내', t.includes('응시자격 제한이 없어요'));
ok('전기기능사: 큐넷 공식 접수처 링크', (await page.locator('.actions a.btn--primary').getAttribute('href')) === 'https://www.q-net.or.kr/');
await page.screenshot({ path: `${OUT}/01_전기기능사_1280.png`, fullPage: true });
// 제2회 탭: 접수 제외일
await page.getByRole('tab', { name: '제2회' }).click();
t = await page.locator('.round-panel:not([hidden])').innerText();
ok('제2회 필기 접수 제외일 3.18 표시', t.includes('3. 18.(목) 접수 제외'));
ok('복수 합격자 발표일(1차·2차) 표시', t.includes('1차 6. 25.(금)') && t.includes('2차 7. 2.(금)'));
// 면제자 검정 경고
await page.getByRole('tab', { name: '필기시험 면제자 검정' }).click();
t = await page.locator('.round-panel:not([hidden])').innerText();
ok('직업계고 면제검정: 자동 응시 불가 안내', t.includes('모든 특성화고·마이스터고 학생이 자동으로 응시할 수 있는 것은 아니며'));
ok('직업계고 면제검정: 필기 없이 실기 5.10~5.14', t.includes('5. 10.(월) ~ 5. 14.(금)') && !t.includes('필기 원서접수'));

// 2 전기기사 — 기사 일정 + 응시조건
await openQ(page, '전기기사'); await pick(page, '전기기사'); t = await detailText(page);
ok('전기기사: 제1~3회, 응시자격 서류제출, 응시자격 안내', ['제1회', '제2회', '제3회', '응시자격 서류제출', '응시자격(학력·경력 등)'].every((x) => t.includes(x)));

// 3 지게차 — 상시검정
await openQ(page, '지게차'); first = await page.locator('#results .item__name').first().innerText();
ok('부분 일치 검색: 지게차 → 지게차운전기능사', first === '지게차운전기능사', first);
await pick(page, '지게차운전기능사'); t = await detailText(page);
ok('지게차: 상시검정 안내 문구', t.includes('상시검정 종목으로, 세부 시험일정은 시행기관의 별도 공고를 확인해 주세요.'));
ok('지게차: 정기 회차 탭 없음', (await page.locator('[role=tab]').count()) === 0);

// 4 컴활 2급 — 별칭 + 기타 기관 상시
await openQ(page, '컴활'); const names = await page.locator('#results .item__name').allInnerTexts();
ok('별칭 검색: 컴활 → 컴퓨터활용능력 1·2급', names.includes('컴퓨터활용능력 1급') && names.includes('컴퓨터활용능력 2급'), names.join(','));
await pick(page, '컴퓨터활용능력 2급'); t = await detailText(page);
ok('컴활2급: 대한상공회의소 상시검정', t.includes('대한상공회의소') && t.includes('상시검정 종목으로'));
ok('컴활2급: 대한상의 접수처 링크', (await page.locator('.actions a.btn--primary').getAttribute('href')) === 'https://license.korcham.net/');
await openQ(page, '컴퓨터 활용 능력 2급');
ok('띄어쓰기 정규화: "컴퓨터 활용 능력 2급"', (await page.locator('#results .item__name').first().innerText()) === '컴퓨터활용능력 2급');

// 5 철도전기신호기능사 — 변경 회차
await openQ(page, '철도전기신호'); await pick(page, '철도전기신호기능사'); t = await detailText(page);
const tabs = await page.locator('[role=tab]').allInnerTexts();
ok('철도전기신호: 제2·4회 + 면제검정만 노출', JSON.stringify(tabs) === JSON.stringify(['제2회', '제4회', '필기시험 면제자 검정']), tabs.join(','));
ok('철도전기신호: 변경사항(2→2·4회) 안내', t.includes('시행 회차 변경'));

// 6 미용사(일반)
await openQ(page, '미용사(일반)'); first = await page.locator('#results .item__name').first().innerText();
ok('특수 종목명: 미용사(일반) 완전일치', first === '미용사(일반)', first);
await openQ(page, '미용사 일반'); first = await page.locator('#results .item__name').first().innerText();
ok('특수 종목명: "미용사 일반"도 검색', first === '미용사(일반)', first);

// 7 제품응용모델링 / 8 신발제조 — 격년 미시행(면제자 검정은 시행)
for (const n of ['제품응용모델링기능사', '신발제조기능사']) {
  await openQ(page, n); await pick(page, n); t = await detailText(page);
  ok(`${n}: 격년제 정기검정 미시행 안내`, t.includes('격년제 시행에 따라 2027년 정기검정(필기·실기)이 시행되지 않습니다'));
  const tb = await page.locator('[role=tab]').allInnerTexts();
  ok(`${n}: 정기 회차 미노출, 면제자 검정만`, JSON.stringify(tb) === '["필기시험 면제자 검정"]', tb.join(','));
}
await openQ(page, '프레스금형기사'); await pick(page, '프레스금형기사'); t = await detailText(page);
ok('프레스금형기사: 격년제 미시행 문구', t.includes('해당 종목은 격년제 시행에 따라 2027년 시험이 시행되지 않습니다.') && (await page.locator('[role=tab]').count()) === 0);

// 9 석공예기능사 — 폐지
await openQ(page, '석공예'); await pick(page, '석공예기능사'); t = await detailText(page);
ok('석공예기능사: 폐지 문구', t.includes('해당 종목은 폐지되어 2027년 시험이 시행되지 않습니다.'));
// 10 타워크레인설치해체 — 검정형 미실시
await openQ(page, '타워크레인설치'); await pick(page, '타워크레인설치해체기능사'); t = await detailText(page);
ok('타워크레인설치해체: 검정형 미실시 문구(폐지 문구 아님)', t.includes('검정형 시험이 시행되지 않습니다') && !t.includes('폐지되어'));

// 11 빅데이터분석기사 — 수정 발표일
await openQ(page, '빅분기'); await pick(page, '빅데이터분석기사'); t = await detailText(page);
ok('빅데이터분석기사: 제14회 최종발표 2027.7.16', t.includes('7. 16.(금)') && t.includes('2027년으로 바로잡았어요'));
await page.getByRole('tab', { name: '제15회' }).click(); t = await page.locator('.round-panel:not([hidden])').innerText();
ok('빅데이터분석기사: 제15회 최종발표 2027.12.17', t.includes('12. 17.(금)'));

// 12 기술사 — 복수 면접 접수
await openQ(page, '건축시공기술사'); await pick(page, '건축시공기술사'); t = await detailText(page);
ok('기술사: 면접 원서접수 ①② 복수 기간', t.includes('① 3. 8.(월) ~ 3. 11.(목)') && t.includes('② 3. 29.(월) ~ 4. 1.(목)'));
ok('기술사: 최종 합격자 발표·면접 표시', t.includes('면접시험') && t.includes('최종 합격자 발표'));

// 13 직업계고 면제검정 대상 — 정보통신기능사(KCA) + 기술훈련 검정
await openQ(page, '정보통신기능사'); await pick(page, '정보통신기능사');
const kt = await page.locator('[role=tab]').allInnerTexts();
ok('KCA 정보통신기능사: 1·2·4회 + 면제자·훈련 검정', ['제1회', '제2회', '제4회', '필기시험 면제자 검정', '기술훈련과정 이수자 검정'].every((x) => kt.includes(x)), kt.join(','));
await openQ(page, '방송통신기능사'); await pick(page, '방송통신기능사'); t = await detailText(page);
ok('방송통신기능사: 원문 불일치 확인 안내', t.includes('확인이 필요한 일정이 있어요'));
// 건축도장: 정기+상시, 필기 없음
await openQ(page, '건축도장'); await pick(page, '건축도장기능사'); t = await detailText(page);
ok('건축도장기능사: 정기+상시 병행, 필기 없음', t.includes('정기검정') && t.includes('상시검정') && t.includes('필기시험 없이 실기시험만') && !t.includes('필기 원서접수'));
// 기사 제3회 필답형 종목별 날짜
await openQ(page, '산림종묘'); await pick(page, '산림종묘기사'); t = await detailText(page);
ok('종목별 별도 시험일: 산림종묘기사 제3회 필답형 11.6', t.includes('제3회 필답형 실기시험일: 11.6.(토)'));
await openQ(page, '임업종묘'); const lim = await page.locator('#results .item__name').allInnerTexts();
ok('구 종목명 별칭: 임업종묘 → 실제 종목(임업종묘기능사) 우선, 별칭(산림종묘기사) 포함', lim[0] === '임업종묘기능사' && lim.includes('산림종묘기사'), lim.join(','));

// 데뷔 로드맵 CTA
ok('로드맵 CTA 노출 + 설정 URL 연결(새 창)', await page.locator('#cta').isVisible() && (await page.locator('#cta-link').getAttribute('href')).startsWith('https://debut.ai.kr/') && (await page.locator('#cta-link').getAttribute('target')) === '_blank');
ok('공식 로고 표시', await page.locator('.logo img[src="assets/logo.svg"]').isVisible() && await page.evaluate(() => document.querySelector('.logo img').naturalWidth > 0));

// 14 존재하지 않는 자격증
await openQ(page, '우주비행사');
ok('검색 결과 없음 안내', await page.locator('#empty').isVisible() && (await page.locator('#count').innerText()).includes('0건'));

// 등급 필터 + 검색어 동시 적용
await page.goto(`${BASE}?year=2027&q=전기&grade=craft`); await page.waitForSelector('#results .item');
let gl = await page.locator('#results .item__meta').allInnerTexts();
ok('검색어+등급 필터 동시 적용(전기, 기능사)', gl.length > 0 && gl.every((m) => m.startsWith('기능사')), `${gl.length}건`);
ok('등급 필터 URL 복원(aria-checked)', (await page.locator('[role=radio][aria-checked=true]').innerText()).startsWith('기능사'));
await page.locator('[role=radio]', { hasText: '기사' }).filter({ hasNotText: '산업' }).first().click();
ok('필터 변경 시 URL 갱신(grade=engineer)', page.url().includes('grade=engineer'));

// URL 직접 접속 (qualification)
const qid = await page.evaluate(async () => (await (await fetch('data/2027/qualifications.json')).json()).find((q) => q.name === '전기기능사').qualification_id);
await page.goto(`${BASE}?year=2027&qualification=${qid}`); await page.waitForSelector('#detail-title');
ok('URL 직접 접속: 종목 상세 복원', (await page.locator('#detail-title').innerText()) === '전기기능사');
ok('URL 직접 접속: 문서 제목 갱신', (await page.title()).startsWith('전기기능사'));
await page.reload(); await page.waitForSelector('#detail-title');
ok('새로고침 후 상태 유지', (await page.locator('#detail-title').innerText()) === '전기기능사');
await page.goto(`${BASE}?year=2027&qualification=QNOTEXIST`); await page.waitForSelector('#results .item');
ok('잘못된 종목 ID 안내', (await detailText(page)).includes('해당 자격증을 찾을 수 없어요'));
// UTM 보존
await page.goto(`${BASE}?utm_source=naver_blog&utm_medium=referral&utm_campaign=2027_certificate_schedule&utm_content=schedule_table_bottom`);
await page.waitForSelector('#results .item'); await page.fill('#q', '용접'); await page.waitForTimeout(400);
ok('UTM 파라미터 보존 + q 반영', page.url().includes('utm_source=naver_blog') && page.url().includes('q=%EC%9A%A9%EC%A0%91'));

// 뒤로 가기
await openQ(page, '전기'); await pick(page, '전기기능사'); await pick(page, '전기기사');
await page.goBack(); await page.waitForTimeout(200);
ok('뒤로 가기: 이전 선택 종목 복원', (await page.locator('#detail-title').innerText()) === '전기기능사');

// 날짜 상태 (KST 기준, ?today=)
await page.goto(`${BASE}?year=2027&qualification=${qid}&today=2027-01-06`); await page.waitForSelector('#detail-title');
t = await detailText(page);
ok('접수 중 상태(2027-01-06)', t.includes('지금 접수 중') && t.includes('접수 중 · 마감 D-2'));
await page.goto(`${BASE}?year=2027&qualification=${qid}&today=2027-03-18`); await page.waitForSelector('#detail-title');
await page.getByRole('tab', { name: '제2회' }).click(); t = await page.locator('.round-panel:not([hidden])').innerText();
ok('접수 제외일 당일 상태(2027-03-18)', t.includes('오늘 접수 제외일'));
await page.goto(`${BASE}?year=2027&qualification=${qid}&today=2027-02-01`); await page.waitForSelector('#detail-title');
await page.getByRole('tab', { name: '제1회' }).click(); t = await page.locator('.round-panel:not([hidden])').innerText();
ok('접수 마감 상태(필기 제1회, 2027-02-01)', t.includes('접수 마감'));

// 키보드 접근성
await page.goto(`${BASE}?year=2027`); await page.waitForSelector('#results .item');
await page.keyboard.press('Tab'); ok('키보드: 첫 Tab = 건너뛰기 링크', (await page.evaluate(() => document.activeElement.className)) === 'skip');
await page.focus('#q'); await page.keyboard.type('전기기능사'); await page.keyboard.press('Enter');
await page.locator('#results .item').first().focus(); await page.keyboard.press('Enter'); await page.waitForSelector('#detail-title');
ok('키보드: 결과 Enter로 선택', (await page.locator('#detail-title').innerText()) === '전기기능사');
await page.getByRole('tab', { name: '제1회' }).focus(); await page.keyboard.press('ArrowRight');
ok('키보드: 회차 탭 방향키 이동', (await page.evaluate(() => document.activeElement.textContent)) === '제2회' && (await page.locator('[role=tab][aria-selected=true]').innerText()) === '제2회');
await page.locator('[role=radio]').first().focus(); await page.keyboard.press('ArrowRight');
ok('키보드: 등급 필터 방향키', (await page.locator('[role=radio][aria-checked=true]').innerText()).startsWith('기능사'));
await page.click('#open-source'); ok('공식 자료 안내 모달 열림', await page.locator('#source-dialog').isVisible());
await page.keyboard.press('Escape'); ok('모달 Esc 닫힘', !(await page.locator('#source-dialog').isVisible()));
const srcTxt = await page.locator('#source-info').innerText();
ok('출처·공고번호·발표일·업데이트일 표기', ['고용노동부 공고 제2026-518호', '2026. 11. 20.(금)', '데이터 최종 업데이트'].every((x) => srcTxt.includes(x)));

// 제거된 기능·푸터
await page.goto(`${BASE}?year=2027&qualification=${qid}`); await page.waitForSelector('#detail-title');
ok('링크 공유·일정 복사·캘린더 버튼 없음', (await page.locator('#detail button', { hasText: /링크 공유|일정 복사|캘린더/ }).count()) === 0);
ok('푸터에 시행기관 목록 없음(공식 자료 안내 창에만)', (await page.locator('#source-info .agency-links').count()) === 0 && (await page.locator('#source-body .agency-links a').count()) === 10);

// 뷰포트
for (const [w, hgt] of [[360, 780], [390, 844], [768, 1024], [1280, 900], [1440, 900], [1920, 1080]]) {
  const p = await newPage({ width: w, height: hgt }, { isMobile: w < 900, hasTouch: w < 900 });
  await p.goto(`${BASE}?year=2027&q=전기기능사`); await p.waitForSelector('#results .item');
  const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await p.screenshot({ path: `${OUT}/vp_${w}_list.png`, fullPage: false });
  await pick(p, '전기기능사');
  const over2 = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const smallTargets = w < 900 ? await p.evaluate(() => [...document.querySelectorAll('#detail button, #detail a')].filter((e) => e.offsetParent && e.getBoundingClientRect().height < 40).map((e) => e.textContent.trim()).slice(0, 5)) : [];
  await p.screenshot({ path: `${OUT}/vp_${w}_detail.png`, fullPage: true });
  ok(`뷰포트 ${w}px: 가로 스크롤 없음`, over <= 0 && over2 <= 0, `list ${over}, detail ${over2}`);
  if (w < 900) {
    ok(`뷰포트 ${w}px: 상세 전환 + 뒤로 버튼`, await p.locator('.back').isVisible() && !(await p.locator('.results').isVisible()));
    ok(`뷰포트 ${w}px: 터치 영역 ≥40px`, smallTargets.length === 0, smallTargets.join(','));
    await p.locator('.back').click(); await p.waitForTimeout(150);
    ok(`뷰포트 ${w}px: 뒤로 → 목록 복귀`, await p.locator('.results').isVisible());
  }
  await p.context().close();
}

// JSON 로딩 실패
const ep = await newPage();
await ep.route('**/data/2027/schedules.json', (r) => r.fulfill({ status: 500, body: 'err' }));
await ep.goto(`${BASE}?year=2027`); await ep.waitForSelector('#empty:not([hidden])');
ok('JSON 로딩 실패 안내 + 다시 시도 버튼', (await ep.locator('#empty').innerText()).includes('데이터를 불러오지 못했어요') && await ep.getByRole('button', { name: '다시 시도' }).isVisible());
const errCountBefore = consoleErrors.filter((e) => !e.includes('500')).length;
await ep.context().close();

// 전 종목 렌더링 스모크(541종목 상세 오류 없음)
const sp = await newPage();
await sp.goto(`${BASE}?year=2027`); await sp.waitForSelector('#results .item');
const ids = await sp.evaluate(() => [...document.querySelectorAll('#results .item')].map((a) => a.dataset.id));
let bad = [];
for (const id of ids) {
  const r = await sp.evaluate(async (id) => {
    document.querySelector(`.item[data-id="${id}"]`).click();
    const t = document.getElementById('detail').innerText;
    return { ok: !!document.getElementById('detail-title') && !t.includes('undefined') && !t.includes('NaN'), t: t.slice(0, 40) };
  }, id);
  if (!r.ok) bad.push(id + ' ' + r.t);
}
ok(`전 종목 상세 렌더링(${ids.length}종목, undefined/NaN 없음)`, ids.length === 541 && bad.length === 0, bad.slice(0, 5).join(' | '));

const realErrors = consoleErrors.filter((e) => !/schedules\.json|500 \(Internal Server Error\)|Failed to load resource/.test(e) || !e.includes('certificate-schedule/?year=2027'));
const unexpected = consoleErrors.filter((e) => !(e.includes('Failed to load resource') && e.includes('500')) && !e.includes('데이터 로딩 실패'));
ok('콘솔 오류 없음(의도한 JSON 실패 테스트 제외)', unexpected.length === 0, unexpected.slice(0, 5).join(' | '));
fs.writeFileSync(`${OUT}/results.json`, JSON.stringify({ base: BASE, at: new Date().toISOString(), results, consoleErrors }, null, 1));
console.log(`\n${results.filter((r) => r.ok).length}/${results.length} passed`);
await browser.close();
process.exit(results.every((r) => r.ok) ? 0 : 1);
