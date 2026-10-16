import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createHorse } from '../../api/horseApi.ts'
import { getUsers } from '../../api/userApi.ts'

const initialForm = {
  name: '', breed: '', dateOfBirth: '', sex: '', coatColor: '',
  sireName: '', damName: '', microchipNumber: '', registrationNumber: '', ownerUserId: '',
}

function CreateHorse() {
  const navigate = useNavigate()
  const [owners, setOwners] = useState([])
  const [ownersLoading, setOwnersLoading] = useState(true)
  const [ownersError, setOwnersError] = useState('')
  const [form, setForm] = useState(initialForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function loadOwners() {
    setOwnersLoading(true)
    setOwnersError('')
    try {
      const rows = await getUsers('HORSE_OWNER')
      setOwners(rows.filter((user) => user.isActive))
    } catch (loadError) {
      setOwnersError(loadError.message || 'Không thể tải danh sách chủ ngựa.')
    } finally {
      setOwnersLoading(false)
    }
  }

  useEffect(() => { void loadOwners() }, [])

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const horse = await createHorse(form)
      navigate(`/manager/horses/${horse.id}/intake`, { replace: true })
    } catch (saveError) {
      setError(saveError.message || 'Không thể tạo hồ sơ ngựa.')
    } finally {
      setSaving(false)
    }
  }

  return <main className="page-content">
    <nav className="breadcrumb" aria-label="Đường dẫn"><Link to="/manager/horses">Danh sách ngựa</Link><span aria-hidden="true">/</span><span>Thêm ngựa</span></nav>
    <header className="page-heading">
      <div><p className="eyebrow">QUẢN LÝ CÂU LẠC BỘ</p><h1>Thêm hồ sơ ngựa</h1><p>Tạo hồ sơ nháp và gắn với chủ ngựa trong câu lạc bộ.</p></div>
    </header>
    <section className="panel">
      <form onSubmit={submit}>
        <div className="horse-form-grid">
          <label className="form-field"><span>Chủ sở hữu <b aria-hidden="true">*</b></span>
            <select required value={form.ownerUserId} onChange={(event) => update('ownerUserId', event.target.value)} disabled={ownersLoading || Boolean(ownersError)}>
              <option value="">{ownersLoading ? 'Đang tải chủ ngựa...' : 'Chọn chủ ngựa'}</option>
              {owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.fullName} ({owner.email})</option>)}
            </select>
            {ownersError && <small role="alert">{ownersError} <button type="button" className="text-button" onClick={() => void loadOwners()}>Thử lại</button></small>}
            {!ownersLoading && !ownersError && owners.length === 0 && <small>Chưa có tài khoản Owner hoạt động để chọn.</small>}
          </label>
          <label className="form-field"><span>Tên ngựa <b aria-hidden="true">*</b></span><input required maxLength={100} value={form.name} onChange={(event) => update('name', event.target.value)} /></label>
          <label className="form-field"><span>Giống</span><input maxLength={100} value={form.breed} onChange={(event) => update('breed', event.target.value)} /></label>
          <label className="form-field"><span>Ngày sinh</span><input type="date" value={form.dateOfBirth} onChange={(event) => update('dateOfBirth', event.target.value)} /></label>
          <label className="form-field"><span>Giới tính</span><select value={form.sex} onChange={(event) => update('sex', event.target.value)}><option value="">Chọn giới tính</option><option value="MALE">Đực</option><option value="FEMALE">Cái</option><option value="GELDING">Đực đã thiến</option></select></label>
          <label className="form-field"><span>Màu lông</span><input maxLength={50} value={form.coatColor} onChange={(event) => update('coatColor', event.target.value)} /></label>
          <label className="form-field"><span>Số microchip</span><input maxLength={30} value={form.microchipNumber} onChange={(event) => update('microchipNumber', event.target.value)} /></label>
          <label className="form-field"><span>Số hộ chiếu / đăng ký</span><input maxLength={50} value={form.registrationNumber} onChange={(event) => update('registrationNumber', event.target.value)} /></label>
          <label className="form-field"><span>Tên ngựa cha</span><input maxLength={100} value={form.sireName} onChange={(event) => update('sireName', event.target.value)} /></label>
          <label className="form-field"><span>Tên ngựa mẹ</span><input maxLength={100} value={form.damName} onChange={(event) => update('damName', event.target.value)} /></label>
        </div>
        <p className="profile-copy">Hồ sơ được lưu ở trạng thái Draft. Ngày sinh, giới tính và microchip cần có trước khi gửi hồ sơ đăng ký.</p>
        {error && <p className="error-message" role="alert">{error}</p>}
        <div className="form-actions">
          <Link className="button button-secondary" to="/manager/horses">Hủy</Link>
          <button className="button" type="submit" disabled={saving || ownersLoading || Boolean(ownersError) || owners.length === 0 || !form.ownerUserId}>{saving ? 'Đang lưu...' : 'Tạo hồ sơ nháp'}</button>
        </div>
      </form>
    </section>
  </main>
}

export default CreateHorse
