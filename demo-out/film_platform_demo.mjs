/**
 * Timed tour of the live Proof-of-Change GitHub Pages replay console,
 * then honesty slides (live140 / gaps / close). Run under Xvfb while ffmpeg records.
 */
import puppeteer from 'puppeteer'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PAGES = 'https://aritracodesbad123.github.io/Proof-of-change/'
const RUN =
  'pr-oyvindwe-connectlife-ha-742-52bc2901d18f-2026-10-22-check-1057'
const SLIDES = pathToFileURL(path.join(__dirname, 'slides.html')).href

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function forceSlide(page, start) {
  await page.evaluate((startAt) => {
    window.__DEMO_LOCK = true
    const slides = [...document.querySelectorAll('.slide')]
    let active = slides[0]
    for (const s of slides) {
      const a = +s.dataset.start
      const b = +s.dataset.end
      if (startAt >= a && startAt < b) active = s
    }
    slides.forEach((s) => s.classList.toggle('active', s === active))
    const cap = document.getElementById('cap')
    if (cap) cap.textContent = active?.dataset.cap || ''
    const bar = document.getElementById('bar')
    if (bar) bar.style.width = `${(startAt / 180) * 100}%`
  }, start)
}

async function main() {
  const t0 = Date.now()
  const until = async (ms) => {
    const wait = ms - (Date.now() - t0)
    if (wait > 0) await sleep(wait)
  }

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome-stable',
    ignoreDefaultArgs: ['--enable-automation'],
    defaultViewport: null,
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=1280,720',
      '--window-position=0,0',
      '--app=data:text/html,<title>boot</title>',
      '--disable-infobars',
      '--no-first-run',
      '--disable-blink-features=AutomationControlled',
      '--disable-features=TranslateUI,ChromeWhatsNewUI',
      '--autoplay-policy=no-user-gesture-required',
    ],
  })

  const pages = await browser.pages()
  const page = pages[0] || (await browser.newPage())
  await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 })
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined })
  })

  // 0:00–0:20 landing / pipeline
  await page.goto(PAGES, { waitUntil: 'networkidle2', timeout: 120000 })
  await page.waitForSelector('.shell, .brand', { timeout: 60000 })
  await until(20000)

  // 0:20–0:45 scroll to finished checks, type filter
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('h2,h3,.label')].find((n) =>
      /finished checks/i.test(n.textContent || ''),
    )
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
  await sleep(1200)
  const search = await page.$('input[type="search"], input[placeholder*="Search" i], input[placeholder*="Filter" i]')
  if (search) {
    await search.click({ clickCount: 3 })
    await search.type('needs attention', { delay: 35 })
  }
  await until(45000)

  // 0:45–1:50 open needs_attention run
  await page.goto(`${PAGES}#/run/${encodeURIComponent(RUN)}`, {
    waitUntil: 'networkidle2',
    timeout: 120000,
  })
  await sleep(2000)
  // If hash router didn't select, click a card matching the id / needs attention
  const opened = await page.evaluate((id) => {
    const article = document.querySelector('.verdict-page, .run-page, article')
    if (article && /needs attention|verdict/i.test(article.innerText || '')) return 'article'
    const cards = [...document.querySelectorAll('button, a, [role="button"], .card, li')]
    const hit = cards.find((c) => (c.textContent || '').includes('connectlife') || (c.getAttribute('href') || '').includes(id))
    if (hit) {
      hit.click()
      return 'clicked'
    }
    return 'miss'
  }, RUN)
  console.log('openRun', opened)
  await sleep(2500)

  // Expand collapsibles / behaviour bits
  await page.evaluate(() => {
    document.querySelectorAll('details:not([open])').forEach((d, i) => {
      if (i < 5) d.open = true
    })
  })
  for (const y of [0, 280, 560, 900, 1200, 800]) {
    await page.evaluate((yy) => window.scrollTo({ top: yy, behavior: 'smooth' }), y)
    await sleep(2200)
  }
  await until(110000)

  // 1:50–2:20 live140 honesty slide (locked; Pages has no live140 record)
  await page.goto(SLIDES, { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    // stop auto timer from fighting the lock
    const id = window.requestAnimationFrame
    window.requestAnimationFrame = (cb) => id(() => {})
  })
  await forceSlide(page, 120)
  await until(140000)

  // 2:20–2:45 gaps
  await forceSlide(page, 150)
  await until(165000)

  // 2:45–3:00 close
  await forceSlide(page, 170)
  await until(180500)

  await browser.close()
  console.log('tour done', ((Date.now() - t0) / 1000).toFixed(1), 's')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
