import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../../api/apiClient.ts'
import { createHorse, getClubs, getHorseById, updateHorse } from '../../api/horseApi.ts'

const emptyForm = {
  name: '',
  breed: '',
  dateOfBirth: '',
  sex: '',
  coatColor: '',
  registrationNumber: '',
  microchipNumber: '',
  sireName: '',
  damName: '',
  clubId: '',
}

const apiFieldNames = {
  HorseName: 'name',
  Breed: 'breed',
  DateOfBirth: 'dateOfBirth',
  Gender: 'sex',
  CoatColor: 'coatColor',
  PassportNumber: 'registrationNumber',
  MicrochipNumber: 'microchipNumber',
  SireName: 'sireName',
  DamName: 'damName',
  ClubID: 'clubId',
}

function dateValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function validate(form) {
  const requiredFields = [
    ['name', 'Tên ngựa'],
    ['breed', 'Giống'],
    ['dateOfBirth', 'Ngày sinh'],
    ['sex', 'Giới tính'],
    ['coatColor', 'Màu lông'],
    ['registrationNumber', 'Số hộ chiếu / đăng ký'],
    ['microchipNumber', 'Microchip'],
    ['sireName', 'Tên ngựa cha'],
    ['damName', 'Tên ngựa mẹ'],
  ]
  const missing = requiredFields.find(([key]) => !String(form[key]).trim())
  if (missing) return `Vui lòng nhập ${missing[1].toLowerCase()}.`
  if (!form.clubId) return 'Vui lòng chọn câu lạc bộ muốn đăng ký.'
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.dateOfBirth)) return 'Ngày sinh phải có định dạng YYYY-MM-DD.'
  const today = new Date()
  const earliest = new Date(today.getFullYear() - 40, today.getMonth(), today.getDate())
  const earliestValue = dateValue(earliest)
  if (form.dateOfBirth > dateValue(today)) return 'Ngày sinh không được ở tương lai.'
  if (form.dateOfBirth < earliestValue) return 'Ngày sinh không được quá 40 năm.'
  if (!/^\d{15}$/.test(form.microchipNumber.trim())) return 'Microchip phải gồm đúng 15 chữ số.'
  if (!/^[A-Z0-9/-]{5,50}$/i.test(form.registrationNumber.trim())) {
    return 'Số hộ chiếu phải dài 5–50 ký tự và chỉ gồm chữ, số, dấu - hoặc /.'
  }
  const horseName = form.name.trim().toLocaleLowerCase()
  const sireName = form.sireName.trim().toLocaleLowerCase()
  const damName = form.damName.trim().toLocaleLowerCase()
  if (sireName === damName || sireName === horseName || damName === horseName) {
    return 'Tên ngựa cha, mẹ phải khác nhau và khác tên ngựa.'
  }
  return ''
}

function OwnerHorseForm({ currentUser, onSaved }) {
  const { horseId } = useParams()
  const navigate = useNavigate()
  const editing = Boolean(horseId)
  const [form, setForm] = useState(emptyForm)
  const [clubs, setClubs] = useState([])
  const [loading, setLoading] = useState(editing)
  const [clubsLoading, setClubsLoading] = useState(!editing)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const submitting = useRef(false)

  const today = useMemo(() => dateValue(new Date()), [])
  const earliestDate = useMemo(() => {
    const date = new Date()
    date.setFullYear(date.getFullYear() - 40)
    return dateValue(date)
  }, [])

  useEffect(() => {
    if (!editing) {
      let active = true
      getClubs().then((result) => {
        if (active) {
          setClubs(result)
          setLoadError('')
        }
      }).catch((loadError) => {
        if (active) setLoadError(loadError instanceof Error ? loadError.message : 'Không thể tải danh sách câu lạc bộ.')
      }).finally(() => {
        if (active) setClubsLoading(false)
      })
      return () => { active = false }
    }

    let active = true
    getHorseById(String(horseId)).then((horse) => {
      if (!active) return
      if (String(horse.ownerUserId) !== String(currentUser.id)) {
        setLoadError('Bạn không có quyền sửa hồ sơ ngựa này.')
        return
      }
      if (horse.profileStatus !== 'DRAFT' && horse.profileStatus !== 'REJECTED') {
        setLoadError('Chỉ hồ sơ nháp hoặc bị từ chối mới có thể chỉnh sửa.')
        return
      }
      setForm({
        name: horse.name,
        breed: horse.breed,
        dateOfBirth: horse.dateOfBirth,
        sex: horse.sex,
        coatColor: horse.coatColor,
        registrationNumber: horse.registrationNumber,
        microchipNumber: horse.microchipNumber,
        sireName: horse.sireName,
        damName: horse.damName,
        clubId: horse.clubId,
      })
      setLoadError('')
    }).catch((loadError) => {
      if (active) setLoadError(loadError instanceof Error ? loadError.message : 'Không thể tải hồ sơ ngựa.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [currentUser.id, editing, horseId])

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

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const validationError = validate(form)
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
      const payload = {
        ...form,
        name: form.name.trim(),
        breed: form.breed.trim(),
        coatColor: form.coatColor.trim(),
        registrationNumber: form.registrationNumber.trim().toUpperCase(),
        microchipNumber: form.microchipNumber.trim(),
        sireName: form.sireName.trim(),
        damName: form.damName.trim(),
      }
      const saved = editing
        ? await updateHorse(String(horseId), payload)
        : await createHorse(payload)
      await onSaved(saved)
      navigate(`/owner/horses/${saved.id}`)
    } catch (saveError) {
      if (saveError instanceof ApiError && Object.keys(saveError.fieldErrors).length) {
        const nextFieldErrors = {}
        let hasUnmappedFieldError = false
        Object.entries(saveError.fieldErrors).forEach(([apiField, messages]) => {
          const field = apiFieldNames[apiField]
          if (field) nextFieldErrors[field] = messages.join(' ')
          else hasUnmappedFieldError = true
        })
        setFieldErrors(nextFieldErrors)
        setError(hasUnmappedFieldError ? saveError.message : '')
      } else {
        setError(saveError instanceof Error ? saveError.message : 'Không thể lưu hồ sơ ngựa.')
      }
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }

  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải hồ sơ ngựa...</section></main>
  if (editing && loadError) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể sửa hồ sơ</h1><p>{loadError}</p><Link className="button button-secondary" to="/owner/horses">Quay lại Ngựa của tôi</Link></section></main>

  return (
    <main className="page-content">
      <nav className="breadcrumb" aria-label="Đường dẫn"><Link to="/owner/horses">Ngựa của tôi</Link><span aria-hidden="true">/</span>{editing ? 'Sửa hồ sơ' : 'Đăng ký ngựa'}</nav>
      <header className="page-heading"><div><p className="eyebrow">CHỦ SỞ HỮU NGỰA · FLOW 1</p><h1>{editing ? 'Sửa hồ sơ ngựa' : 'Đăng ký ngựa'}</h1><p>{editing ? 'Lưu thay đổi vào hồ sơ nháp hoặc bị từ chối; việc gửi đăng ký được thực hiện riêng.' : 'Lưu hồ sơ nháp trước, sau đó gửi đăng ký từ trang chi tiết.'}</p></div></header>
      <section className="panel form-panel">
        {loadError && <p className="error-message" role="alert">{loadError}</p>}
        {error && <p className="error-message" role="alert">{error}</p>}
        <form onSubmit={submit}>
          <div className="horse-form-grid">
            <label className="form-field"><span>Tên ngựa</span><input required value={form.name} aria-invalid={Boolean(fieldErrors.name)} onChange={(event) => setField('name', event.target.value)} />{fieldErrors.name && <small className="field-error" role="alert">{fieldErrors.name}</small>}</label>
            <label className="form-field"><span>Giống</span><input required value={form.breed} aria-invalid={Boolean(fieldErrors.breed)} onChange={(event) => setField('breed', event.target.value)} />{fieldErrors.breed && <small className="field-error" role="alert">{fieldErrors.breed}</small>}</label>
            <label className="form-field"><span>Ngày sinh</span><input type="date" min={earliestDate} max={today} required value={form.dateOfBirth} aria-invalid={Boolean(fieldErrors.dateOfBirth)} onChange={(event) => setField('dateOfBirth', event.target.value)} />{fieldErrors.dateOfBirth && <small className="field-error" role="alert">{fieldErrors.dateOfBirth}</small>}</label>
            <label className="form-field"><span>Giới tính</span><select required value={form.sex} aria-invalid={Boolean(fieldErrors.sex)} onChange={(event) => setField('sex', event.target.value)}><option value="">Chọn giới tính</option><option value="MALE">Đực</option><option value="FEMALE">Cái</option><option value="GELDING">Đực đã thiến</option></select>{fieldErrors.sex && <small className="field-error" role="alert">{fieldErrors.sex}</small>}</label>
            <label className="form-field"><span>Màu lông</span><input required value={form.coatColor} aria-invalid={Boolean(fieldErrors.coatColor)} onChange={(event) => setField('coatColor', event.target.value)} />{fieldErrors.coatColor && <small className="field-error" role="alert">{fieldErrors.coatColor}</small>}</label>
            <label className="form-field"><span>Số hộ chiếu / đăng ký</span><input required minLength="5" maxLength="50" pattern="(?:[A-Za-z0-9]|/|-)+" value={form.registrationNumber} aria-invalid={Boolean(fieldErrors.registrationNumber)} onChange={(event) => setField('registrationNumber', event.target.value.toUpperCase())} />{fieldErrors.registrationNumber && <small className="field-error" role="alert">{fieldErrors.registrationNumber}</small>}</label>
            <label className="form-field"><span>Microchip</span><input type="text" inputMode="numeric" autoComplete="off" maxLength="15" pattern="[0-9]{15}" required value={form.microchipNumber} aria-invalid={Boolean(fieldErrors.microchipNumber)} onChange={(event) => setField('microchipNumber', event.target.value)} /><small>Nhập đủ 15 chữ số; số 0 ở đầu được giữ nguyên.</small>{fieldErrors.microchipNumber && <small className="field-error" role="alert">{fieldErrors.microchipNumber}</small>}</label>
            <label className="form-field"><span>Tên ngựa cha</span><input required value={form.sireName} aria-invalid={Boolean(fieldErrors.sireName)} onChange={(event) => setField('sireName', event.target.value)} />{fieldErrors.sireName && <small className="field-error" role="alert">{fieldErrors.sireName}</small>}</label>
            <label className="form-field"><span>Tên ngựa mẹ</span><input required value={form.damName} aria-invalid={Boolean(fieldErrors.damName)} onChange={(event) => setField('damName', event.target.value)} />{fieldErrors.damName && <small className="field-error" role="alert">{fieldErrors.damName}</small>}</label>
            {!editing && <label className="form-field"><span>CLB muốn đăng ký</span><select required value={form.clubId} disabled={clubsLoading || clubs.length === 0} aria-invalid={Boolean(fieldErrors.clubId)} onChange={(event) => setField('clubId', event.target.value)}><option value="">{clubsLoading ? 'Đang tải câu lạc bộ...' : 'Chọn câu lạc bộ'}</option>{clubs.map((club) => <option key={club.id} value={club.id}>{club.name}</option>)}</select>{fieldErrors.clubId && <small className="field-error" role="alert">{fieldErrors.clubId}</small>}</label>}
            {!editing && !clubsLoading && clubs.length === 0 && !loadError && !error && <p className="error-message" role="alert">Không có câu lạc bộ đang hoạt động để đăng ký.</p>}
          </div>
          <div className="form-actions">
            <Link className="button button-secondary" to={editing ? `/owner/horses/${horseId}` : '/owner/horses'}>Hủy</Link>
            <button className="button" type="submit" disabled={saving || (!editing && (clubsLoading || clubs.length === 0))}>{saving ? 'Đang lưu...' : editing ? 'Lưu thay đổi' : 'Lưu hồ sơ nháp'}</button>
          </div>
        </form>
      </section>
    </main>
  )
}

export default OwnerHorseForm
