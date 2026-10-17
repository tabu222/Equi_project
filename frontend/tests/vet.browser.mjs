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
import { clubToday } from '../src/pages/vet/vetDomain.js'

const base = 'http://127.0.0.1:5174'
const chrome = process.env.BROWSER_EXECUTABLE || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
assert.ok(chrome, 'Set BROWSER_EXECUTABLE to a Chromium browser executable')
const temp = await mkdtemp(join(tmpdir(), 'equi-vet-browser-'))
const artifacts = process.env.BROWSER_ARTIFACT_DIR || join(temp, 'screenshots')
await mkdir(artifacts, { recursive: true })
const browser = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${join(temp, 'profile')}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
const exceptions = []
let socket
let nextId = 0
const waiting = new Map()
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
async function api(path, token, method = 'GET', body, expected = 200) {
  const response = await fetch(base + '/api' + path, { method,
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}) })
  const result = await response.json()
  assert.equal(response.status, expected, `${method} ${path}: ${JSON.stringify(result)}`)
  return result
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
      void cdp('Page.handleJavaScriptDialog', { accept: false })
    }
  }
  await cdp('Page.enable'); await cdp('Runtime.enable')
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })

  const tokenFor = async email => (await api('/auth/login', null, 'POST', { Email: email, Password: 'test-only-password' })).access
  const testDay = clubToday()
  const followUp = new Date(Date.parse(`${testDay}T00:00:00Z`) + 3 * 86400000).toISOString().slice(0, 10)
  const owner = await tokenFor('owner@one.test')
  const manager = await tokenFor('manager@one.test')
  const vet = await tokenFor('vet@one.test')
  const vet2 = await tokenFor('vet2@one.test')
  const outside = await tokenFor('vet@two.test')
  const club = (await api('/auth/me', owner)).ClubID
  const payload = (name, chip) => ({ ClubID: club, HorseName: name, Breed: 'Thoroughbred', Gender: 'Female', DateOfBirth: '2021-03-10', CoatColor: 'Bay', SireName: 'Storm King', DamName: 'Lady Rain', MicrochipNumber: chip, PassportNumber: `VT-${chip}` })
  async function pending(name, chip) {
    const horse = await api('/horses', owner, 'POST', payload(name, chip), 201)
    await api(`/horses/${horse.HorseID}/submit`, owner, 'POST', {})
    await api(`/horses/${horse.HorseID}/verify`, manager, 'POST', {})
    return horse.HorseID
  }
  const approvedId = await pending('Vet Healthy Restricted', '985000000000081')
  const approvedRecord = await api(`/horses/${approvedId}/medical-records`, vet, 'POST', {
    ExamType: 'Initial Exam', ExamDate: `${testDay}T08:10:15`, HealthStatus: 'Healthy', TrainingEligibility: 'Restricted', RestrictionNote: 'Restriction entered by veterinarian', Conclusion: 'Clinical conclusion', FollowUpDate: followUp,
  }, 201)
  await api(`/medical-records/${approvedRecord.MedicalRecordID}/sign`, vet, 'POST', {})
  await api(`/horses/${approvedId}/approve`, manager, 'POST', { HorseCode: 'VET-081', StallID: 1 })
  const horseId = await pending('Vet Intake Pending', '985000000000082')
  const queue = (await api('/vet/pending-initial-exams', vet)).find(r => r.HorseID === horseId)
  await login('vet@one.test')
  await waitSelector('.vet-stats')
  assert.equal(await evaluate(`document.querySelector('.vet-stat.health-ELIGIBLE strong').textContent`), '1')
  await click('a[href="/vet/herd?health=ELIGIBLE"]')
  await waitSelector('.vet-workspace .horse-table tbody tr')
  assert.equal(await evaluate(`document.querySelectorAll('.vet-workspace .horse-table tbody tr').length`), 1)
  await until(() => evaluate(`document.querySelector('.training-Restricted')?.textContent.includes('Hạn chế tập')`), 'healthy horse still restricted')
  await screenshot('vet-herd-desktop.png')
  await navigate('/vet/stalls')
  await waitSelector('.vet-stall')
  assert.equal(await evaluate(`document.querySelectorAll('.vet-stall').length`), 2) // One occupied stall plus one unassigned horse.
  await screenshot('vet-stalls-desktop.png')
  await navigate('/vet/horses-needing-exam')
  await waitSelector('.vet-queue-table tbody tr')
  assert.ok((await evaluate(`document.querySelector('.vet-queue-table tbody').textContent`)).includes('Chờ khám'))
  assert.equal(await evaluate(`document.querySelector('.vet-queue-table .horse-table-identity small').textContent`), 'Chưa cập nhật')
  await click(`a[href="/vet/horses/${horseId}/examination"]`)
  await waitSelector('input[type=datetime-local]')
  assert.ok(!(await evaluate(`document.querySelector('.page-heading').textContent`)).includes(`Mã ngựa #${horseId}`))
  await fill('input[type=datetime-local]', `${testDay}T09:12:45`)
  await fill('input[type=number]', '480.5')
  await fill('textarea[maxlength="1500"]', 'Observed symptom')
  await fill('input[maxlength="500"]', 'Left forelimb text finding')
  await evaluate(`(() => { const fields = document.querySelectorAll('textarea[maxlength="1500"]');
    const set = (el, value) => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, value); el.dispatchEvent(new Event('input', { bubbles:true })); };
    set(fields[1], 'Diagnosis entered by vet'); set(fields[2], 'Conclusion entered by vet'); set(fields[3], 'Clinical exam note'); })()`)
  await fill('select', 'Monitor')
  await evaluate(`(() => { const el=document.querySelectorAll('select')[1]; Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,'Restricted'); el.dispatchEvent(new Event('change',{bubbles:true})); })()`)
  await fill('textarea[maxlength="1000"]', 'Restriction entered by vet')
  await fill('input[type=date]', followUp)
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el=>el.textContent==='Lưu nháp').click()`)
  await until(() => evaluate(`document.querySelector('.success-message')?.textContent.includes('Đã lưu')`), 'draft save')
  const [draft] = await api(`/horses/${horseId}/medical-records`, vet)
  assert.equal(draft.RegistrationRequestID, queue.RegistrationRequestID)
  assert.equal(draft.ExamDate, `${testDay}T09:12:45`)
  assert.equal(Number(draft.WeightKg), 480.5)
  await navigate(`/vet/horses/${horseId}/examination`)
  await waitSelector('input[type=datetime-local]')
  assert.equal(await evaluate(`document.querySelector('input[type=datetime-local]').value`), `${testDay}T09:12:45`)
  assert.equal(await evaluate(`document.querySelector('input[maxlength="500"]').value`), 'Left forelimb text finding')
  await api(`/medical-records/${draft.MedicalRecordID}`, vet2, 'PATCH', { Diagnosis: 'Forbidden edit' }, 409)
  await api(`/horses/${horseId}/medical-records`, outside, 'GET', null, 404)
  await api(`/medical-records/${draft.MedicalRecordID}`, outside, 'GET', null, 404)

  // Real race: another Vet opens an unclaimed form before a draft is created.
  const raceId = await pending('Vet Race Claim', '985000000000083')
  await navigate(`/vet/horses/${raceId}/examination`)
  await waitSelector('input[type=datetime-local]')
  await api(`/horses/${raceId}/medical-records`, vet2, 'POST', { ExamType: 'Initial Exam' }, 201)
  await evaluate(`Array.from(document.querySelectorAll('button')).find(el=>el.textContent==='Lưu nháp').click()`)
  await until(() => evaluate(`document.querySelector('h1')?.textContent.includes('Vet khác xử lý')`), 'competing Vet claim shown')
  await navigate('/vet/horses-needing-exam')
  await waitSelector('.vet-queue-table')
  assert.ok((await evaluate(`document.querySelector('.vet-queue-table tbody').textContent`)).includes('Vet khác đang xử lý'))

  await navigate(`/vet/horses/${horseId}/examination`)
  await waitSelector('input[type=datetime-local]')
  await click('form button[type=submit]')
  await until(() => evaluate(`document.querySelector('.intake-vet-conclusion')?.textContent.includes('Đã chốt')`), 'sign clinical record')
  const signedHorse = await api(`/horses/${horseId}`, vet)
  assert.equal(signedHorse.RegistrationStatus, 'PendingExam')
  assert.equal(signedHorse.HorseCode, null)
  assert.equal((await api('/vet/pending-initial-exams', vet)).some(r => r.HorseID === horseId), false)
  await api(`/medical-records/${draft.MedicalRecordID}`, vet, 'PATCH', { Diagnosis: 'Overwrite signed' }, 409)
  await navigate('/vet/intake-results')
  await waitSelector(`a[href="/vet/horses/${horseId}/examination"]`)
  assert.ok((await evaluate(`document.querySelector('.vet-workspace .horse-table tbody').textContent`)).includes('Chờ Manager xử lý'))
  await click(`a[href="/vet/horses/${horseId}/examination"]`)
  await waitSelector('.intake-vet-conclusion')
  assert.equal(await evaluate(`document.querySelectorAll('form').length`), 0)
  await navigate(`/vet/horses/${horseId}?tab=history`)
  await waitSelector('.vet-record-button')
  await click('.vet-record-button')
  await waitSelector('.vet-amendments form')
  await fill('.vet-amendments input', 'Correct a clinical note')
  await fill('.vet-amendments textarea', 'Corrected note, preserving the signed original')
  await until(() => evaluate(`!document.querySelector('.vet-amendments form button').disabled`), 'ready to append')
  await click('.vet-amendments form button')
  await until(() => evaluate(`document.querySelector('.vet-amendments .success-message')?.textContent.includes('Đã lưu')`), 'amendment save')
  await navigate(`/vet/horses/${horseId}?tab=history`)
  await waitSelector('.vet-record-button')
  await click('.vet-record-button')
  await until(() => evaluate(`document.querySelector('.vet-amendment')?.textContent.includes('Corrected note')`), 'persisted amendment after reload')
  assert.equal((await api(`/horses/${horseId}/medical-records`, vet))[0].Note, 'Clinical exam note')
  await screenshot('vet-record-desktop.png')
  await navigate('/vet/calendar?due=upcoming')
  await waitSelector('.vet-workspace .horse-table')
  assert.ok((await evaluate(`document.querySelector('.vet-workspace').textContent`)).includes('Vet Healthy Restricted'))

  // Real browser offline failure cannot become healthy counts of zero.
  await cdp('Network.enable')
  await cdp('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 })
  await evaluate(`document.querySelector('.vet-workspace .page-heading button').click()`)
  await until(() => evaluate(`!!document.querySelector('.vet-workspace [role=alert]')`), 'offline error state')
  assert.equal(await evaluate(`document.querySelectorAll('.vet-stats').length`), 0)
  await cdp('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
  await evaluate(`document.querySelector('.vet-workspace .page-heading button').click()`)
  await until(() => evaluate(`!!document.querySelector('.vet-workspace .horse-table')`), 'retry after connection restores')
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  for (const path of ['/vet/overview', '/vet/stalls', `/vet/horses/${horseId}?tab=history`]) {
    await navigate(path)
    await waitSelector('.vet-workspace')
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, `mobile overflow ${path}`)
  }
  await screenshot('vet-profile-mobile.png')
  assert.deepEqual(exceptions, [], 'No uncaught browser errors')
  console.log('PASS: real Vet login; accurate herd/health/training filters; stalls/unassigned; intake draft/reload/time/units; other Vet ownership; cross-club 404; competing draft conflict; signed immutability; results discoverable before Manager approval; append/reload amendment; due dates; offline/retry; mobile 390px.')
  console.log(`Screenshots: ${artifacts}`)
} finally {
  try { await cdp('Browser.close') } catch { browser.kill() }
  socket?.close()
  const profile = resolve(temp, 'profile')
  assert.equal(profile.startsWith(resolve(temp) + (process.platform === 'win32' ? '\\' : '/')), true)
  await delay(300)
  await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 300 })
}
