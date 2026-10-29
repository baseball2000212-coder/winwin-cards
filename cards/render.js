// HTML 카드 → 1080×1350 PNG. 사용법: node cards/render.js out/a.html out/b.html ...
// 렌더 전에 .fit 문장을 한 줄에 들어갈 때까지 1px씩 줄이고(최소 24px),
// 넘침·겹침을 검사해 WARN 줄로 출력한다.
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const measure = process.argv[2] === '--measure';
  const files = process.argv.slice(measure ? 3 : 2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  if (measure) {  // 차트 자리(.chart[data-src])의 실제 크기를 JSON으로 출력
    const sizes = {};
    for (const f of files) {
      await page.goto('file://' + path.resolve(f));
      await page.evaluate(() => document.fonts.ready);
      Object.assign(sizes, await page.evaluate(() => Object.fromEntries(
        [...document.querySelectorAll('.chart[data-src]')].map(e => {
          const r = e.getBoundingClientRect();
          return [e.dataset.src, [Math.floor(r.width), Math.floor(r.height)]];
        }))));
    }
    console.log(JSON.stringify(sizes));
    await browser.close();
    return;
  }
  for (const f of files) {
    await page.goto('file://' + path.resolve(f));
    // 스토리(1080×1920)처럼 높이가 다른 페이지는 <body data-h="1920">로 지정한다
    const h = await page.evaluate(() => +document.body.dataset.h || 1350);
    await page.setViewportSize({ width: 1080, height: h });
    await page.evaluate(() => document.fonts.ready);
    const warns = await page.evaluate(() => {
      const out = [];
      document.querySelectorAll('.fit').forEach(s => {
        let size = parseFloat(getComputedStyle(s).fontSize);
        while (s.scrollWidth > s.clientWidth && size > 24) { size -= 1; s.style.fontSize = size + 'px'; }
        if (s.scrollWidth > s.clientWidth) out.push('한 줄 문장이 넘침: ' + s.textContent.slice(0, 30));
      });
      const card = document.querySelector('.card');
      const foot = document.querySelector('.foot');
      const limit = foot ? foot.getBoundingClientRect().top - 12 : 1350 - 100;
      const body = document.querySelector('.body');
      if (body && body.scrollHeight > body.clientHeight + 2) out.push(`본문이 넘침 (${body.scrollHeight} > ${body.clientHeight})`);
      card.querySelectorAll('.box, .callout, .bullets, h1, .sub, .chips, .tiles').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.bottom > limit) out.push(`하단 페이지 표시와 겹침: ${el.className} bottom=${Math.round(r.bottom)}`);
        if (r.right > 1080 - 84 + 2) out.push(`오른쪽 여백 침범: ${el.className}`);
      });
      card.querySelectorAll('.box').forEach(el => {
        if (el.scrollHeight > el.clientHeight + 2) out.push(`박스 안 내용이 잘림: ${el.className} (${el.scrollHeight} > ${el.clientHeight})`);
      });
      card.querySelectorAll('h1').forEach(h => {
        const lh = parseFloat(getComputedStyle(h).lineHeight);
        const lines = Math.round(h.getBoundingClientRect().height / lh);
        if (lines > 2) out.push(`제목이 ${lines}줄: ${h.textContent.slice(0, 30)}`);
      });
      card.querySelectorAll('.nowrap-cell').forEach(c => {
        if (c.scrollWidth > c.clientWidth + 1) out.push('표 칸 넘침: ' + c.textContent.slice(0, 20));
      });
      return out;
    });
    const png = f.replace(/\.html$/, '.png');
    await page.screenshot({ path: png });
    console.log((warns.length ? 'WARN ' : 'ok   ') + path.basename(png) + (warns.length ? '\n  - ' + warns.join('\n  - ') : ''));
  }
  await browser.close();
})();
