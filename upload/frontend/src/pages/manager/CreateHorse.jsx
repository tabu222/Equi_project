import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/apiClient'
import { createHorse } from '../../api/horseApi'
import { createUser, getUsers } from '../../api/userApi'
import { cleanHorsePayload, dateValue, mapFieldErrors, validateHorseForm } from '../../components/horse/horseFormRules.js'

// FE1-03 + FE1-05: Manager lập lý lịch ngựa, chọn chủ ngựa có sẵn hoặc tạo tài khoản chủ ngựa mới.
// Hồ sơ lưu ở trạng thái Nháp; gửi / xác minh / duyệt làm tiếp ở trang "Xử lý Flow 1".

const emptyForm = {
  ownerId: '', name: '', breed: '', dateOfBirth: '', sex: '', coatColor: '',
  registrationNumber: '', microchipNumber: '', sireName: '', damName: '',
}
const emptyOwner = { fullName: '', email: '', phone: '', address: '', password: '' }

function NewOwnerPanel({ onCreated, onCancel }) {
  const [owner, setOwner] = useState(emptyOwner)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  function setField(field, value) {
    setOwner((current) => ({ ...current, [field]: value }))
    setFieldErrors((current) => ({ ...current, [field]: undefined }))
  }

  async function save() {
    if (!owner.fullName.trim() || !owner.email.trim() || !owner.phone.trim() || !owner.address.trim()) {
      setError('Nhập đủ họ tên, email, số điện thoại và địa chỉ của chủ ngựa.')
      return
    }
    if (!/^(0\d{9}|\+84\d{9})$/.test(owner.phone.trim())) {
      setError('Số điện thoại phải dạng 0xxxxxxxxx (10 số) hoặc +84xxxxxxxxx.')
      return
    }
    if (owner.password && owner.password.length < 6) {
      setError('Mật khẩu tối thiểu 6 ký tự (để trống thì hệ thống tự tạo mật khẩu tạm).')
      return
    }
    setSaving(true)
    setError('')
    try {
      const created = await createUser({
        fullName: owner.fullName.trim(),
        email: owner.email.trim(),
        phone: owner.phone.trim(),
        address: owner.address.trim(),
        roleCode: 'HORSE_OWNER',
        password: owner.password || undefined,
      })
      onCreated(created)
    } catch (saveError) {
      if (saveError instanceof ApiError && Object.keys(saveError.fieldErrors).length) {
        const map = { FullName: 'fullName', Email: 'email', Phone: 'phone', Address: 'address', Password: 'password' }
        const next = {}
        Object.entries(saveError.fieldErrors).forEach(([key, messages]) => { if (map[key]) next[map[key]] = messages.join(' ') })
        setFieldErrors(next)
        setError(Object.keys(next).length ? '' : saveError.message)
      } else {
        setError(saveError instanceof Error ? saveError.message : 'Không thể tạo tài khoản chủ ngựa.')
      }
    } finally {
      setSaving(false)
    }
  }

  const input = (field, label, props = {}) => (
    <label className="form-field"><span>{label}</span>
      <input value={owner[field]} aria-invalid={Boolean(fieldErrors[field])} onChange={(event) => setField(field, event.target.value)} {...props} />
      {fieldErrors[field] && <small className="field-error" role="alert">{fieldErrors[field]}</small>}
    </label>
  )

  return (
    <section className="panel form-panel" aria-label="Tạo tài khoản chủ ngựa" style={{ marginBottom: 16 }}>
      <h2>Tạo tài khoản chủ ngựa mới</h2>
      <p className="profile-copy">Chủ ngựa đăng nhập bằng email này để xem hồ sơ và gửi yêu cầu sửa lý lịch.</p>
      {error && <p className="error-message" role="alert">{error}</p>}
      <div className="horse-form-grid">
        {input('fullName', 'Họ và tên')}
        {input('email', 'Email', { type: 'email', autoComplete: 'off' })}
        {input('phone', 'Số điện thoại', { inputMode: 'tel', placeholder: '0903123456' })}
        {input('address', 'Địa chỉ')}
        {input('password', 'Mật khẩu (không bắt buộc)', { type: 'password', autoComplete: 'new-password' })}
      </div>
      <div className="form-actions">
        <button className="button button-secondary" type="button" onClick={onCancel} disabled={saving}>Hủy</button>
        <button className="button" type="button" onClick={() => void save()} disabled={saving}>{saving ? 'Đang tạo...' : 'Tạo chủ ngựa'}</button>
      </div>
    </section>
  )
}

function CreateHorse({ onSaved }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyForm)
  const [owners, setOwners] = useState([])
  const [ownersLoading, setOwnersLoading] = useState(true)
  const [ownersError, setOwnersError] = useState('')
  const [showNewOwner, setShowNewOwner] = useState(false)
  const [ownerNotice, setOwnerNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const submitting = useRef(false)

  const today = useMemo(() => dateValue(new Date()), [])
  const earliestDate = useMemo(() => {
    const date = new Date()
    date.setFullYear(date.getFullYear() - 40)
    return dateValue(date)
  }, [])

  useEffect(() => {
    let active = true
    getUsers('HORSE_OWNER').then((rows) => {
      if (active) setOwners(rows.filter((user) => user.isActive))
    }).catch((loadError) => {
      if (active) setOwnersError(loadError instanceof Error ? loadError.message : 'Không thể tải danh sách chủ ngựa.')
    }).finally(() => {
      if (active) setOwnersLoading(false)
    })
    return () => { active = false }
  }, [])

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
    setError('')
    setFieldErrors((current) => {
      if (!current[field]) return current
      const next = { ...current }
      delete next[field]
      return next
    })
  }

  function ownerCreated(user) {
    setOwners((current) => [...current, user])
    setField('ownerId', user.id)
    setShowNewOwner(false)
    setOwnerNotice(user.temporaryPassword
      ? `Đã tạo tài khoản ${user.email}. Mật khẩu tạm (chỉ hiện một lần, hãy báo cho chủ ngựa): ${user.temporaryPassword}`
      : `Đã tạo tài khoản ${user.email} và chọn làm chủ ngựa.`)
  }

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const validationError = validateHorseForm(form, { requireOwner: true })
    if (validationError) {
      setError(validationError)
      setFieldErrors({})
      return
    }
    submitting.current = true
    setSaving(true)
    setError('')
    setFieldErrors({})
    try {
      const saved = await createHorse(cleanHorsePayload(form))
      await onSaved?.(saved)
      navigate(`/manager/horses/${saved.id}/intake`)
    } catch (saveError) {
      if (saveError instanceof ApiError && Object.keys(saveError.fieldErrors).length) {
        const { fieldErrors: mapped, unmapped } = mapFieldErrors(saveError.fieldErrors)
        setFieldErrors(mapped)
        setError(unmapped ? saveError.message : '')
      } else {
        setError(saveError instanceof Error ? saveError.message : 'Không thể tạo hồ sơ ngựa.')
      }
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }

  const field = (key, label, control) => (
    <label className="form-field"><span>{label}</span>{control}
      {fieldErrors[key] && <small className="field-error" role="alert">{fieldErrors[key]}</small>}
    </label>
  )
  const text = (key, extra = {}) => <input required value={form[key]} aria-invalid={Boolean(fieldErrors[key])} onChange={(event) => setField(key, event.target.value)} {...extra} />

  return (
    <main className="page-content">
      <nav className="breadcrumb" aria-label="Đường dẫn"><Link to="/manager/horses">Danh sách ngựa</Link><span aria-hidden="true">/</span>Thêm ngựa</nav>
      <header className="page-heading"><div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ · FLOW 1</p><h1>Thêm hồ sơ ngựa</h1><p>Lập lý lịch và gắn chủ ngựa. Hồ sơ lưu ở trạng thái Nháp, sau đó gửi và xác minh ở trang Xử lý Flow 1.</p></div></header>

      {showNewOwner && <NewOwnerPanel onCreated={ownerCreated} onCancel={() => setShowNewOwner(false)} />}

      <section className="panel form-panel">
        {ownerNotice && <p className="success-message" role="status">{ownerNotice}</p>}
        {ownersError && <p className="error-message" role="alert">{ownersError}</p>}
        {error && <p className="error-message" role="alert">{error}</p>}
        <form onSubmit={submit}>
          <div className="horse-form-grid">
            {field('ownerId', 'Chủ ngựa', <>
              <select required value={form.ownerId} disabled={ownersLoading} aria-invalid={Boolean(fieldErrors.ownerId)} onChange={(event) => setField('ownerId', event.target.value)}>
                <option value="">{ownersLoading ? 'Đang tải chủ ngựa...' : 'Chọn chủ ngựa'}</option>
                {owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.fullName} ({owner.email})</option>)}
              </select>
              {!showNewOwner && <button type="button" className="text-button" onClick={() => { setShowNewOwner(true); setOwnerNotice('') }}>+ Tạo chủ ngựa mới</button>}
            </>)}
            {field('name', 'Tên ngựa', text('name'))}
            {field('breed', 'Giống', text('breed'))}
            {field('dateOfBirth', 'Ngày sinh', text('dateOfBirth', { type: 'date', min: earliestDate, max: today }))}
            {field('sex', 'Giới tính', <select required value={form.sex} aria-invalid={Boolean(fieldErrors.sex)} onChange={(event) => setField('sex', event.target.value)}><option value="">Chọn giới tính</option><option value="MALE">Đực</option><option value="FEMALE">Cái</option><option value="GELDING">Đực đã thiến</option></select>)}
            {field('coatColor', 'Màu lông', text('coatColor'))}
            {field('registrationNumber', 'Số hộ chiếu / đăng ký', <input required minLength="5" maxLength="50" value={form.registrationNumber} aria-invalid={Boolean(fieldErrors.registrationNumber)} onChange={(event) => setField('registrationNumber', event.target.value.toUpperCase())} />)}
            {field('microchipNumber', 'Microchip (15 chữ số)', text('microchipNumber', { inputMode: 'numeric', autoComplete: 'off', maxLength: 15, pattern: '[0-9]{15}' }))}
            {field('sireName', 'Tên ngựa cha', text('sireName'))}
            {field('damName', 'Tên ngựa mẹ', text('damName'))}
          </div>
          <div className="form-actions">
            <Link className="button button-secondary" to="/manager/horses">Hủy</Link>
            <button className="button" type="submit" disabled={saving || ownersLoading}>{saving ? 'Đang lưu...' : 'Lưu hồ sơ nháp'}</button>
          </div>
        </form>
      </section>
    </main>
  )
}

export default CreateHorse
