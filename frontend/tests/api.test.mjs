import { after, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { File } from 'node:buffer'
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { transformWithOxc } from 'vite'

// Exercise the actual FE adapters with controlled HTTP responses. No business data is mocked in the app.
const temp = await mkdtemp(join(tmpdir(), 'equi-api-tests-'))
for (const name of ['apiClient.ts', 'userApi.ts', 'horseApi.ts', 'registrationApi.js']) {
  const source = await readFile(new URL(`../src/api/${name}`, import.meta.url), 'utf8')
  const compiled = (await transformWithOxc(source, name, { lang: name.endsWith('.ts') ? 'ts' : 'js' }))
    .code.replaceAll('import.meta.env', '({})').replaceAll('./apiClient.ts', './apiClient.mjs')
  await writeFile(join(temp, name.replace(/\.(ts|js)$/, '.mjs')), compiled)
}
const client = await import(pathToFileURL(join(temp, 'apiClient.mjs')))
const users = await import(pathToFileURL(join(temp, 'userApi.mjs')))
const horses = await import(pathToFileURL(join(temp, 'horseApi.mjs')))
const registration = await import(pathToFileURL(join(temp, 'registrationApi.mjs')))
const store = new Map()
const events = []
const originalFetch = globalThis.fetch
globalThis.localStorage = {
  getItem: (key) => store.get(key) ?? null,
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
}
globalThis.window = { location: { origin: 'https://equi.example.test' }, dispatchEvent: (event) => events.push(event.type) }
const json = (value, status = 200) => new Response(JSON.stringify(value), { status })
const rawUser = { UserID: 1, ClubID: 2, Email: 'owner@example.test', Roles: ['HORSE_OWNER'], Status: 'Active' }
const rawHorse = { HorseID: 3, HorseName: 'Thunder', RegistrationStatus: 'Draft' }
beforeEach(() => { store.clear(); events.length = 0 })
after(async () => { globalThis.fetch = originalFetch; await rm(temp, { recursive: true, force: true }) })

test('multi-field proposals send files and purpose metadata together without modifying the live document API', async () => {
  client.saveSession('access', 'refresh')
  const changes = { HorseName: 'Thunder II', CoatColor: 'Grey' }
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/horses/3/profile-change-requests')
    assert.ok(init.body instanceof FormData)
    assert.equal(init.headers.get('Authorization'), 'Bearer access')
    assert.equal(init.headers.has('Content-Type'), false)
    const payload = JSON.parse(init.body.get('Payload'))
    assert.deepEqual(payload.Changes, changes)
    assert.deepEqual(payload.RemoveImageIDs, [4])
    assert.deepEqual(payload.EvidenceDocumentIDs, [5])
    assert.equal(payload.Attachments[0].FileKey, 'file0')
    assert.equal(payload.Attachments[0].Purpose, 'replace')
    assert.equal(payload.Attachments[0].ReplacesDocumentID, 8)
    assert.equal(init.body.get('file0').name, 'corrected.pdf')
    return json({ ProfileChangeRequestID: 9, HorseID: 3, Status: 'Pending',
      ChangedFields: { Reason: 'Correct certificate', Changes: Object.entries(changes).map(([Field, NewValue]) => ({ Field, OldValue: 'old', NewValue })),
        Attachments: [{ ...payload.Attachments[0], FileUrl: '/api/profile-change-requests/9/attachments/0' }],
        EvidenceDocuments: [{ DocumentID: 5, DocumentName: 'Proof' }] } })
  }
  const result = await horses.submitProfileProposal('3', { Changes: changes, Reason: 'Correct certificate', RemoveImageIDs: [4], EvidenceDocumentIDs: [5] },
    [{ file: new File(['%PDF-1.4'], 'corrected.pdf', { type: 'application/pdf' }), Purpose: 'replace', DocumentName: 'Corrected certificate', DocumentType: 'Passport', ReplacesDocumentID: 8 }])
  assert.equal(result.changes.length, 2)
  assert.equal(result.attachments[0].Purpose, 'replace')
  assert.equal(result.evidenceDocuments[0].DocumentID, 5)
})

test('proposal files use authenticated scoped endpoints and reject arbitrary URLs', async () => {
  client.saveSession('access', 'refresh')
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/profile-change-requests/9/attachments/0?download=1')
    assert.equal(init.headers.get('Authorization'), 'Bearer access')
    return new Response('private proof', { headers: { 'Content-Type': 'application/pdf' } })
  }
  assert.equal(await (await horses.getProposalFile('/api/profile-change-requests/9/attachments/0', true)).text(), 'private proof')
  assert.throws(() => horses.getProposalFile('https://other.example/file'), /không được hỗ trợ/)
  assert.throws(() => horses.getProposalFile('/api/horse-documents/../accounts'), /không được hỗ trợ/)
})

test('withdrawing a proposal preserves the real enum and reviewer history', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/profile-change-requests/9/withdraw')
    assert.equal(init.method, 'POST')
    return json({ ProfileChangeRequestID: 9, HorseID: 3, Status: 'Withdrawn', ReviewedAt: '2026-10-16T12:00:00', ReviewedByName: 'Owner', ChangedFields: { Changes: [], Reason: 'Correction' } })
  }
  const result = await horses.withdrawProfileProposal('9')
  assert.equal(result.status, 'Withdrawn')
  assert.equal(result.reviewedByName, 'Owner')
})

test('login uses the public contract and saves exactly one token pair', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/auth/login')
    assert.equal(init.headers.has('Authorization'), false)
    assert.deepEqual(JSON.parse(init.body), { Email: 'owner@example.test', Password: 'test-input' })
    return json({ access: 'access', refresh: 'refresh', User: rawUser })
  }
  assert.equal((await users.login('owner@example.test', 'test-input')).user.role, 'OWNER')
  assert.deepEqual([...store.keys()].sort(), ['equi.access-token', 'equi.refresh-token'])
})

test('mixed staff roles and unknown roles do not break user lists', async () => {
  const roles = ['CLUB_MANAGER', 'TRAINER', 'HEAD_TRAINER', 'GROOM', 'WORK_RIDER', 'VETERINARIAN', 'FUTURE_ROLE']
  globalThis.fetch = async () => json(roles.map((role, index) => ({ ...rawUser, UserID: index + 1, Roles: [role] })))
  assert.deepEqual((await users.getUsers()).map((user) => user.role),
    ['CLUB_MANAGER', 'TRAINER', 'HEAD_TRAINER', 'GROOM', 'WORK_RIDER', 'VET', 'UNSUPPORTED'])
})

test('parallel 401 requests share one refresh and retry once', async () => {
  client.saveSession('expired', 'refresh')
  let refreshes = 0
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++
      await new Promise((resolve) => setImmediate(resolve))
      return json({ access: 'renewed' })
    }
    return init.headers.get('Authorization') === 'Bearer renewed' ? json({ ok: true }) : json({}, 401)
  }
  const result = await Promise.all([client.apiGet('/one'), client.apiGet('/two')])
  assert.deepEqual(result, [{ ok: true }, { ok: true }])
  assert.equal(refreshes, 1)
  assert.deepEqual(events, [])
})

test('failed refresh expires the session without retry loops', async () => {
  client.saveSession('expired', 'invalid')
  let calls = 0
  globalThis.fetch = async () => { calls++; return json({ detail: 'Expired' }, 401) }
  await assert.rejects(client.apiGet('/one'), { status: 401 })
  assert.equal(calls, 2)
  assert.equal(client.getAccessToken(), null)
  assert.deepEqual(events, ['equi:session-expired'])
})

test('network failure during refresh preserves the current session for retry', async () => {
  client.saveSession('expired', 'refresh')
  globalThis.fetch = async (url) => {
    if (url.endsWith('/auth/refresh')) throw new TypeError('Offline')
    return json({}, 401)
  }
  await assert.rejects(client.apiGet('/one'), { name: 'ApiError' })
  assert.equal(client.getAccessToken(), 'expired')
  assert.deepEqual(events, [])
})

test('late refresh response cannot restore a logged out session', async () => {
  client.saveSession('expired', 'refresh')
  let release
  let entered
  const started = new Promise((resolve) => { entered = resolve })
  globalThis.fetch = async (url) => {
    if (url.endsWith('/auth/refresh')) {
      entered()
      return new Promise((resolve) => { release = () => resolve(json({ access: 'late' })) })
    }
    return json({}, 401)
  }
  const pending = client.apiGet('/one')
  await started
  client.clearSession()
  release()
  await assert.rejects(pending, { status: 401 })
  assert.equal(client.getAccessToken(), null)
})

test('403 and field validation errors remain visible without refreshing', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return json({ detail: 'Không đủ quyền.', code: 'DENIED' }, 403) }
  await assert.rejects(client.apiGet('/restricted'), { status: 403, code: 'DENIED' })
  assert.equal(calls, 1)
  globalThis.fetch = async () => json({ MicrochipNumber: ['Already used.'] }, 400)
  await assert.rejects(horses.createHorse({ name: 'Thunder' }), (error) => {
    assert.deepEqual(error.fieldErrors, { MicrochipNumber: ['Already used.'] })
    return true
  })
})

test('HTML and plain-text server tracebacks never become user-facing error messages', async () => {
  for (const body of ['<!doctype html><html>ProgrammingError Invalid column IsRetired</html>',
    'Traceback: private database diagnostics at C:/backend/settings.py']) {
    globalThis.fetch = async () => new Response(body, { status: 500, headers: { 'Content-Type': 'text/html' } })
    await assert.rejects(client.apiGet('/horses/8/documents'), (error) => {
      assert.equal(error.status, 500)
      assert.match(error.message, /Máy chủ đang gặp lỗi/)
      assert.doesNotMatch(error.message, /ProgrammingError|Traceback|IsRetired|settings.py/)
      return true
    })
  }
})

test('Manager horse creation maps owner, pedigree and enums to backend columns', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/horses')
    assert.deepEqual(JSON.parse(init.body), {
      HorseName: 'Thunder', Gender: 'Male', OwnerID: 7, SireName: 'Sire', DamName: 'Dam',
      PassportNumber: 'VN-12345', MicrochipNumber: '985141000123401',
    })
    return json(rawHorse, 201)
  }
  await horses.createHorse({ name: 'Thunder', sex: 'MALE', ownerUserId: '7', sireName: 'Sire', damName: 'Dam',
    registrationNumber: 'vn-12345', microchipNumber: '985141000123401' })
})

test('registration sends required fields, ignores caller role and stores no credentials', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/auth/register')
    assert.equal(init.headers.has('Authorization'), false)
    const body = JSON.parse(init.body)
    assert.equal(body.ClubID, 2)
    assert.equal(body.Address, 'Address')
    assert.equal('RoleCode' in body, false)
    return json({ User: rawUser, access: 'access', refresh: 'refresh' }, 201)
  }
  await registration.registerOwner({ fullName: 'Owner', email: 'owner@example.test', phone: '0901234567',
    address: 'Address', clubId: '2', password: 'test-input', RoleCode: 'CLUB_MANAGER' })
  assert.equal(store.size, 0)
})

test('public club lookup never sends an existing access token', async () => {
  client.saveSession('expired', 'refresh')
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/clubs')
    assert.equal(init.headers.has('Authorization'), false)
    return json([{ ClubID: 2, ClubName: 'Club' }])
  }
  assert.deepEqual(await horses.getClubs(), [{ id: '2', name: 'Club' }])
})

test('horse document uploads use authenticated multipart data without forcing a content type', async () => {
  client.saveSession('access', 'refresh')
  globalThis.fetch = async (url, init) => {
    assert.equal(url, '/api/horses/3/documents')
    assert.equal(init.body instanceof FormData, true)
    assert.equal(init.body.get('File').name, 'horse.pdf')
    assert.equal(init.body.get('DocumentType'), 'Passport')
    assert.equal(init.body.get('DocumentName'), 'horse.pdf')
    assert.equal(init.headers.has('Content-Type'), false)
    assert.match(init.headers.get('Authorization'), /^Bearer /)
    return json({
      DocumentID: 9,
      DocumentName: 'horse.pdf',
      DocumentType: 'Passport',
      FileUrl: '/api/horse-documents/9/file',
      UploadedBy: 7,
      IsUploadedFile: true,
      IsVisibleToOwner: true,
      ContentType: 'application/pdf',
    }, 201)
  }
  const file = new File(['%PDF-1.4'], 'horse.pdf', { type: 'application/pdf' })
  const document = await horses.uploadHorseDocument('3', file, 'Passport', 'horse.pdf')
  assert.equal(document.documentId, '9')
  assert.equal(document.uploadedById, '7')
  assert.equal(document.isUploadedFile, true)
})

test('horse document downloads use the authenticated file endpoint and delete the selected document', async () => {
  client.saveSession('access', 'refresh')
  let calls = 0
  globalThis.fetch = async (url, init) => {
    calls++
    assert.match(init.headers.get('Authorization'), /^Bearer /)
    if (url === '/api/horse-documents/9/file?download=1') return new Response('saved file', { status: 200 })
    assert.equal(url, '/api/horse-documents/9')
    assert.equal(init.method, 'DELETE')
    return new Response(null, { status: 204 })
  }
  assert.equal(await (await horses.getHorseDocumentFile('9', true)).text(), 'saved file')
  await horses.deleteHorseDocument('9')
  assert.equal(calls, 2)
})

test('registration is blocked while document uploads are pending or in flight', async () => {
  client.saveSession('access', 'refresh')
  horses.setHorseDocumentUploadsPending('3', true)
  await assert.rejects(horses.submitHorse('3'), /Còn file chưa được lưu/)
  horses.setHorseDocumentUploadsPending('3', false)

  let finishUpload
  let uploadStarted
  const started = new Promise((resolve) => { uploadStarted = resolve })
  globalThis.fetch = async (url) => {
    assert.equal(url, '/api/horses/3/documents')
    uploadStarted()
    return new Promise((resolve) => { finishUpload = () => resolve(json({
      DocumentID: 10,
      DocumentName: 'horse.pdf',
      DocumentType: 'Passport',
      FileUrl: '/api/horse-documents/10/file',
      IsUploadedFile: true,
    }, 201)) })
  }
  const file = new File(['%PDF-1.4'], 'horse.pdf', { type: 'application/pdf' })
  const upload = horses.uploadHorseDocument('3', file, 'Passport', 'horse.pdf')
  await started
  await assert.rejects(horses.submitHorse('3'), /Còn file chưa được lưu/)
  finishUpload()
  await upload
})

test('relative file links resolve from the configured API base and absolute links stay absolute', () => {
  assert.equal(client.resolveFileUrl('/api/files/horse.pdf'), 'https://equi.example.test/api/files/horse.pdf')
  assert.equal(client.resolveFileUrl('files/horse.pdf'), 'https://equi.example.test/api/files/horse.pdf')
  assert.equal(client.resolveFileUrl('https://files.example.test/horse.pdf'), 'https://files.example.test/horse.pdf')
})
