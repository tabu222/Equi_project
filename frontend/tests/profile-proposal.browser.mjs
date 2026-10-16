// Real browser + real API smoke test; no browser libraries or mocked HTTP responses.
// Start backend: .venv/Scripts/python.exe -m apps.core.tests.browser_fixture
// Start frontend with VITE_API_PROXY_TARGET=http://127.0.0.1:8001 on port 5174.
// Run: node tests/profile-proposal.browser.mjs
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const base = 'http://127.0.0.1:5174'
const chrome = process.env.BROWSER_EXECUTABLE || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
assert.ok(chrome, 'Set BROWSER_EXECUTABLE to a Chromium browser executable')
const temp = await mkdtemp(join(tmpdir(), 'equi-proposal-browser-'))
const artifacts = process.env.BROWSER_ARTIFACT_DIR || join(temp, 'screenshots')
await mkdir(artifacts, { recursive: true })
const browser = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${join(temp, 'profile')}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
const exceptions = []
let socket
let nextId = 0
const waiting = new Map()
let cancelledDialogs = 0
let acceptNextDialog = false
async function until(predicate, label, timeout = 15000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const result = await predicate()
    if (result) return result
    await delay(100)
  }
  throw new Error(`Timed out: ${label}`)
}
function cdp(method, params = {}) {
  const id = ++nextId
  return new Promise((resolvePromise, reject) => {
    const timer = setTimeout(() => { waiting.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    waiting.set(id, { resolve: (value) => { clearTimeout(timer); resolvePromise(value) }, reject })
    socket.send(JSON.stringify({ id, method, params }))
    if (process.env.CDP_DEBUG) console.log('CDP send', id, method)
  })
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result.value
}
const waitSelector = (selector) => until(() => evaluate(`!!document.querySelector(${JSON.stringify(selector)})`), selector)
async function fill(selector, value) {
  await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) throw Error('Missing control');
    Object.getOwnPropertyDescriptor(el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set.call(el, ${JSON.stringify(value)});
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); })()`)
  await delay(30)
}
async function click(selector) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)
  await delay(60)
}
async function upload(selector, paths) {
  const result = await cdp('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(selector)})` })
  await cdp('DOM.setFileInputFiles', { objectId: result.result.objectId, files: paths })
  await delay(80)
}
async function navigate(path) {
  await cdp('Page.navigate', { url: base + path })
  await delay(150)
}
async function login(email) {
  await navigate('/login')
  await waitSelector('.auth-login input[name=email]')
  await fill('.auth-login input[name=email]', email)
  await fill('.auth-login input[name=password]', 'test-only-password')
  await click('.auth-login button[type=submit]')
  await waitSelector('.app-shell')
}
async function screenshot(name) {
  await evaluate('window.scrollTo(0,0)')
  await delay(200)
  const result = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  await writeFile(join(artifacts, name), Buffer.from(result.data, 'base64'))
}
async function api(path, token) {
  const response = await fetch(base + '/api' + path, { headers: { Authorization: `Bearer ${token}` } })
  assert.equal(response.status, 200, path)
  return response.json()
}
try {
  const portFile = join(temp, 'profile', 'DevToolsActivePort')
  const port = await until(async () => { try { return (await readFile(portFile, 'utf8')).split('\n')[0] } catch { return '' } }, 'Chromium startup')
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
  const target = targets.find((item) => item.type === 'page')
  socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolvePromise, reject) => { socket.onopen = resolvePromise; socket.onerror = reject })
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (process.env.CDP_DEBUG) console.log('CDP receive', message.id || message.method)
    if (message.id) {
      const pending = waiting.get(message.id)
      waiting.delete(message.id)
      if (message.error) pending?.reject(new Error(message.error.message))
      else pending?.resolve(message.result)
    } else if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text)
    else if (message.method === 'Page.javascriptDialogOpening') {
      cancelledDialogs++
      const accept = acceptNextDialog
      acceptNextDialog = false
      void cdp('Page.handleJavaScriptDialog', { accept })
    }
  }
  await cdp('Page.enable'); await cdp('Runtime.enable')
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await login('owner@one.test')
  await navigate('/owner/horses/1/correction-request')
  await waitSelector('.correction-form')
  assert.equal(await evaluate('document.querySelector(".correction-page h1").textContent'), 'Yêu cầu cập nhật hồ sơ')
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('Thêm thông tin cần sửa')).click()`)
  await fill('.correction-row input:not([readonly])', 'Thunder revised')
  // Real router navigation must warn and stay on the form when cancelled.
  await click('a.correction-page__back')
  await until(() => cancelledDialogs > 0, 'unsaved navigation warning')
  assert.ok((await evaluate('location.pathname')).endsWith('/correction-request'))
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('Thêm thông tin cần sửa')).click()`)
  await fill('.correction-row:nth-of-type(2) select', 'CoatColor')
  await fill('.correction-row:nth-of-type(2) input:not([readonly])', 'Grey')
  const photo = resolve('public/landing-horse.jpg')
  const pdf = join(temp, 'corrected.pdf')
  await writeFile(pdf, '%PDF-1.4\n%%EOF')
  await upload('input[type=file]:not([multiple])', [photo])
  await upload('input[type=file][accept=".jpg,.jpeg,.png,.webp"][multiple]', [photo])
  await upload('input[type=file][accept=".pdf,.jpg,.jpeg,.png"]', [pdf])
  await fill('.correction-file-list > article:nth-child(3) .correction-doc-fields select', 'replace')
  await fill('.correction-file-list > article:nth-child(3) .correction-doc-fields label:nth-child(4) select', '2')
  await fill('.correction-file-list > article:nth-child(3) textarea', 'Updated registration details')
  await upload('input[type=file][accept=".pdf,.jpg,.jpeg,.png"]', [pdf])
  await fill('.correction-file-list > article:nth-child(4) .correction-doc-fields select', 'add')
  await upload('input[type=file][accept=".pdf,.jpg,.jpeg,.png"]', [pdf])
  await fill('textarea[placeholder]', 'Correct name and coat color, add photos and replace the registration certificate.')
  await screenshot('owner-desktop.png')
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await screenshot('owner-mobile.png')
  const overflow = await evaluate(`(() => { const page = document.querySelector('.correction-page'); const bounds = page.getBoundingClientRect(); return { width: page.clientWidth, scroll: page.scrollWidth, offenders: [...page.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > bounds.right + 1).slice(0, 10).map(el => ({ tag: el.tagName, className: el.className, width: el.getBoundingClientRect().width })) } })()`)
  assert.ok(overflow.scroll <= overflow.width, 'Mobile form has no horizontal overflow: ' + JSON.stringify(overflow))
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  const ownerToken = await evaluate('localStorage.getItem("equi.access-token")')
  // A real network failure must preserve the complete proposal for a retry.
  await cdp('Network.enable')
  await cdp('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 })
  await click('.correction-form button[type=submit]')
  await waitSelector('.correction-page__error')
  assert.equal(await evaluate('document.querySelectorAll(".correction-file-list > article").length'), 5)
  assert.equal(await evaluate('document.querySelector(".correction-row input:not([readonly])").value'), 'Thunder revised')
  await cdp('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
  await click('.correction-form button[type=submit]')
  await waitSelector('.correction-page__success')
  assert.ok((await evaluate('document.querySelector(".correction-page__success").textContent')).includes('Chờ duyệt'))
  assert.equal((await api('/horses/1', ownerToken)).HorseName, 'Thunder')
  assert.equal((await api('/horses/1/documents', ownerToken)).length, 2)
  await screenshot('owner-pending.png')
  await evaluate('localStorage.clear()')
  await login('manager@one.test')
  await navigate('/manager/profile-change-requests')
  await waitSelector('.proposal-details')
  assert.equal(await evaluate('document.querySelectorAll(".proposal-table tbody tr").length'), 2)
  assert.equal(await evaluate('document.querySelectorAll(".proposal-details .proposal-attachment-grid > .proposal-file").length'), 5)
  await screenshot('manager-review.png')
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Duyệt').click()`)
  const managerToken = await evaluate('localStorage.getItem("equi.access-token")')
  const horse = await until(async () => { const result = await api('/horses/1', managerToken); return result.HorseName === 'Thunder revised' ? result : null }, 'manager approval saved')
  assert.equal(horse.HorseName, 'Thunder revised'); assert.equal(horse.CoatColor, 'Grey')
  const docs = await api('/horses/1/documents', managerToken)
  assert.equal(docs.length, 5)
  assert.equal(docs.filter((doc) => doc.IsPrimary).length, 1)
  assert.ok(docs.some((doc) => doc.ReplacesDocumentID === 2))
  assert.ok(await evaluate('document.querySelector(".proposal-review-list > article").clientWidth > 600'), 'Manager comparison uses the available page width')
  await evaluate('localStorage.clear()')
  await login('owner@one.test')
  await navigate('/owner/horses/1/correction-request')
  await waitSelector('.correction-form')
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('Thêm thông tin cần sửa')).click()`)
  await fill('.correction-row input:not([readonly])', 'Withdraw this name')
  await fill('textarea[placeholder]', 'Owner withdrawal check')
  await click('.correction-form button[type=submit]')
  await waitSelector('.correction-page__success')
  acceptNextDialog = true
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim() === 'Rút yêu cầu').click()`)
  await until(() => evaluate(`document.querySelector('.correction-page__success')?.textContent.includes('Đã rút yêu cầu')`), 'owner withdrawal')
  const freshToken = await evaluate('localStorage.getItem("equi.access-token")')
  assert.equal((await api('/horses/1', freshToken)).HorseName, 'Thunder revised')
  assert.equal((await api('/profile-change-requests', freshToken))[0].Status, 'Withdrawn')
  assert.deepEqual(exceptions, [], 'No uncaught browser errors')
  console.log('PASS: real Owner login, two fields + avatar + gallery + replacement + addition + evidence, unsaved navigation, network failure/retry, desktop/mobile, pending isolation, Manager review/approval, Owner withdrawal.')
  console.log(`Screenshots: ${artifacts}`)
} finally {
  try { await cdp('Browser.close') } catch { browser.kill() }
  socket?.close()
  // Keep screenshots; remove only the disposable Chromium profile, within our own temp directory.
  const profile = resolve(temp, 'profile')
  assert.equal(profile.startsWith(resolve(temp) + (process.platform === 'win32' ? '\\' : '/')), true)
  await delay(300)
  await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 300 })
}
