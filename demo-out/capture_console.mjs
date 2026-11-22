/** Capture real Pages console frames for the demo film. */
import puppeteer from 'puppeteer'
import fs from 'node:fs'
import path from 'node:path'

const OUT = '/workspace/demo-out/capture'
const PAGES = 'https://aritracodesbad123.github.io/Proof-of-change/'
const RUN = 'pr-oyvindwe-connectlife-ha-742-52bc2901d18f-2026-10-22-check-1057'

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function shot(page, name) {
  const dest = path.join(OUT, `${name}.png`)
  await page.screenshot({ path: dest, type: 'png' })
  console.log('shot', name)
  return dest
}

const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome-stable',
  defaultViewport: { width: 1280, height: 720, deviceScaleFactor: 1 },
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
})
fs.mkdirSync(OUT, { recursive: true })
const page = await browser.newPage()
await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 })

await page.goto(PAGES, { waitUntil: 'networkidle2', timeout: 120000 })
await page.waitForSelector('body')
await sleep(1500)
await shot(page, '01-landing')

// scroll to finished checks
await page.evaluate(() => {
  const h = [...document.querySelectorAll('h2,h3')].find((n) => /finished checks/i.test(n.textContent || ''))
  h?.scrollIntoView({ block: 'start' })
})
await sleep(800)
await shot(page, '02-finished-list')

const search = await page.$('input[type="search"], input[placeholder*="Search" i]')
if (search) {
  await search.click({ clickCount: 3 })
  await search.type('needs attention', { delay: 20 })
  await sleep(800)
  await shot(page, '03-filtered')
}

// click first needs attention button
await page.evaluate(() => {
  const btn = [...document.querySelectorAll('button')].find((b) =>
    /needs attention/i.test(b.textContent || ''),
  )
  btn?.click()
})
await sleep(2000)
// fallback hash nav
if (!(await page.$('.verdict-page, article.verdict-page'))) {
  await page.goto(`${PAGES}#/run/${encodeURIComponent(RUN)}`, { waitUntil: 'networkidle2' })
  await sleep(2000)
}
await shot(page, '04-run-top')

await page.evaluate(() => window.scrollTo(0, 420))
await sleep(600)
await shot(page, '05-run-mid')

await page.evaluate(() => {
  document.querySelectorAll('details').forEach((d, i) => {
    if (i < 6) d.open = true
  })
  window.scrollTo(0, 900)
})
await sleep(800)
await shot(page, '06-run-evidence')

await page.evaluate(() => window.scrollTo(0, 1400))
await sleep(600)
await shot(page, '07-run-lower')

await browser.close()
console.log('captures in', OUT)
