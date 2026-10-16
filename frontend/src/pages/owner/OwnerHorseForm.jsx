import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../../api/apiClient.ts'
import {
  createHorse,
  deleteHorseDocument,
  getClubs,
  getHorseById,
  getHorseDocuments,
  setHorseDocumentUploadsPending,
  updateHorse,
  uploadHorseDocument,
} from '../../api/horseApi.ts'
import HorseDocuments from '../../components/horse/HorseDocuments.jsx'

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

const documentTypes = [
  { value: 'Passport', label: 'Hộ chiếu / giấy đăng ký ngựa' },
  { value: 'Microchip Certificate', label: 'Chứng nhận microchip' },
  { value: 'Ownership Proof', label: 'Chứng minh sở hữu' },
  { value: 'Handover Record', label: 'Biên bản bàn giao' },
  { value: 'Contract', label: 'Hợp đồng' },
  { value: 'Other', label: 'Tài liệu khác' },
]

const allowedExtensions = new Set(['.pdf', '.jpg', '.jpeg', '.png', '.webp'])
const imageExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp'])

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
  if (form.dateOfBirth > dateValue(today)) return 'Ngày sinh không được ở tương lai.'
  if (form.dateOfBirth < dateValue(earliest)) return 'Ngày sinh không được quá 40 năm.'
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

function formatSize(size) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function fileValidationError(file, imagesOnly) {
  const extension = `.${file.name.split('.').pop()}`.toLowerCase()
  if (!allowedExtensions.has(extension) || (imagesOnly && !imageExtensions.has(extension))) {
    return imagesOnly
      ? 'Ảnh cần có định dạng JPG, PNG hoặc WebP.'
      : 'Chỉ nhận PDF, JPG, PNG hoặc WebP.'
  }
  if (file.size === 0) return 'File rỗng, vui lòng chọn file khác.'
  return ''
}

function documentNameFor(file, isImage) {
  const prefix = isImage ? 'Ảnh ngựa - ' : ''
  const extension = `.${file.name.split('.').pop()}`.toLowerCase()
  const keptExtension = allowedExtensions.has(extension) ? extension : ''
  const availableNameLength = Math.max(0, 150 - prefix.length - keptExtension.length)
  const baseName = keptExtension
    ? file.name.slice(0, -keptExtension.length).slice(0, availableNameLength)
    : file.name.slice(0, availableNameLength)
  return `${prefix}${baseName}${keptExtension}`
}

function OwnerHorseForm({ currentUser, onSaved }) {
  const { horseId } = useParams()
  const navigate = useNavigate()
  const routeEditing = Boolean(horseId)
  const [draftId, setDraftId] = useState('')
  const savedHorseId = horseId || draftId
  const editing = Boolean(savedHorseId)
  const [form, setForm] = useState(emptyForm)
  const [clubs, setClubs] = useState([])
  const [horseStatus, setHorseStatus] = useState('')
  const [documents, setDocuments] = useState([])
  const [pendingUploads, setPendingUploads] = useState([])
  const [documentType, setDocumentType] = useState('Passport')
  const [loading, setLoading] = useState(routeEditing)
  const [clubsLoading, setClubsLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploadBusy, setUploadBusy] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [documentsError, setDocumentsError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const submitting = useRef(false)
  const uploadSequence = useRef(0)
  const today = useMemo(() => dateValue(new Date()), [])
  const earliestDate = useMemo(() => {
    const date = new Date()
    date.setFullYear(date.getFullYear() - 40)
    return dateValue(date)
  }, [])

  useEffect(() => {
    let active = true
    getClubs().then((result) => {
      if (active) setClubs(result)
    }).catch((clubsError) => {
      if (active) setLoadError(clubsError instanceof Error ? clubsError.message : 'Không thể tải danh sách câu lạc bộ.')
    }).finally(() => {
      if (active) setClubsLoading(false)
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!routeEditing) return undefined
    let active = true
    Promise.all([getHorseById(String(horseId)), getHorseDocuments(String(horseId))]).then(([horse, savedDocuments]) => {
      if (!active) return
      if (String(horse.ownerUserId) !== String(currentUser.id)) {
        setLoadError('Bạn không có quyền sửa hồ sơ ngựa này.')
        return
      }
      if (horse.profileStatus !== 'DRAFT' && horse.profileStatus !== 'REJECTED') {
        setLoadError('Chỉ hồ sơ nháp hoặc bị từ chối mới có thể chỉnh sửa.')
        return
      }
      setHorseStatus(horse.profileStatus)
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
      setDocuments(savedDocuments)
      setLoadError('')
      setDocumentsError('')
    }).catch((loadErrorValue) => {
      if (active) setLoadError(loadErrorValue instanceof Error ? loadErrorValue.message : 'Không thể tải hồ sơ hoặc tài liệu ngựa.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [currentUser.id, horseId, routeEditing])

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

  function addFiles(fileList, isImage) {
    const entries = Array.from(fileList).map((file) => {
      uploadSequence.current += 1
      const validationError = fileValidationError(file, isImage)
      return {
        key: `${Date.now()}-${uploadSequence.current}`,
        file,
        kind: isImage ? 'image' : 'document',
        documentType: isImage ? 'Other' : documentType,
        documentName: documentNameFor(file, isImage),
        status: validationError ? 'invalid' : 'ready',
        error: validationError,
      }
    })
    if (savedHorseId) setHorseDocumentUploadsPending(savedHorseId, true)
    setPendingUploads((current) => [...current, ...entries])
    setError('')
  }

  function removeUpload(uploadKey) {
    const remaining = pendingUploads.filter((item) => item.key !== uploadKey)
    if (savedHorseId && remaining.length === 0) {
      setHorseDocumentUploadsPending(savedHorseId, false)
      setError('')
    }
    setPendingUploads((current) => current.filter((item) => item.key !== uploadKey))
  }

  async function retryUpload(upload) {
    if (!await sendUpload(upload)) return
    const remaining = pendingUploads.filter((item) => item.key !== upload.key)
    setHorseDocumentUploadsPending(savedHorseId, remaining.length > 0)
  }

  async function sendUpload(upload, horseIdForUpload = savedHorseId) {
    if (!horseIdForUpload) return false
    setUploadBusy(true)
    setPendingUploads((current) => current.map((item) => (
      item.key === upload.key ? { ...item, status: 'uploading', error: '' } : item
    )))
    let previousIds
    try {
      const existingDocuments = await getHorseDocuments(horseIdForUpload)
      const existingIds = existingDocuments.map((document) => document.documentId)
      if (upload.previousDocumentIds) {
        const originalIds = new Set(upload.previousDocumentIds)
        const confirmedDocument = existingDocuments.find((document) => (
          !originalIds.has(document.documentId)
          && document.documentName === upload.documentName
          && document.documentType === upload.documentType
        ))
        if (confirmedDocument) {
          setDocuments(existingDocuments)
          setPendingUploads((current) => current.filter((item) => item.key !== upload.key))
          setDocumentsError('')
          setError('')
          setUploadBusy(false)
          return true
        }
      }
      previousIds = new Set(upload.previousDocumentIds || existingIds)
      if (!upload.previousDocumentIds) {
        setPendingUploads((current) => current.map((item) => (
          item.key === upload.key
            ? { ...item, previousDocumentIds: [...previousIds] }
            : item
        )))
      }
      setDocuments(existingDocuments)
    } catch (refreshError) {
      setPendingUploads((current) => current.map((item) => (
        item.key === upload.key
          ? { ...item, status: 'failed', error: `Không tải được danh sách tài liệu trước khi gửi file. ${refreshError instanceof Error ? refreshError.message : ''}` }
          : item
      )))
      setUploadBusy(false)
      return false
    }
    try {
      const document = await uploadHorseDocument(
        horseIdForUpload,
        upload.file,
        upload.documentType,
        upload.documentName,
      )
      setDocuments((current) => [...current, document])
      setPendingUploads((current) => current.filter((item) => item.key !== upload.key))
      setDocumentsError('')
      setError('')
      return true
    } catch (uploadError) {
      let confirmedDocument
      try {
        const latestDocuments = await getHorseDocuments(horseIdForUpload)
        confirmedDocument = latestDocuments.find((item) => (
          !previousIds.has(item.documentId)
          && item.documentName === upload.documentName
          && item.documentType === upload.documentType
        ))
        if (confirmedDocument) setDocuments(latestDocuments)
      } catch (refreshError) {
        setDocumentsError(
          `Không xác nhận được trạng thái file sau lỗi tải lên. ${refreshError instanceof Error ? refreshError.message : 'Không thể tải lại danh sách tài liệu.'}`,
        )
      }
      if (confirmedDocument) {
        setPendingUploads((current) => current.filter((item) => item.key !== upload.key))
        setError('')
        return true
      }
      setPendingUploads((current) => current.map((item) => (
        item.key === upload.key
          ? {
            ...item,
            status: 'failed',
            error: uploadError instanceof Error ? uploadError.message : 'Tải file thất bại.',
          }
          : item
      )))
      return false
    } finally {
      setUploadBusy(false)
    }
  }

  async function deleteDocument(document) {
    setDeletingId(document.documentId)
    setDocumentsError('')
    try {
      await deleteHorseDocument(document.documentId)
      setDocuments((current) => current.filter((item) => item.documentId !== document.documentId))
    } catch (deleteError) {
      setDocumentsError(deleteError instanceof Error ? deleteError.message : 'Không thể xóa tài liệu.')
    } finally {
      setDeletingId('')
    }
  }

  async function submit(event) {
    event.preventDefault()
    if (submitting.current || uploadBusy) return
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
      const saved = savedHorseId
        ? await updateHorse(savedHorseId, payload)
        : await createHorse(payload)
      if (!savedHorseId) setDraftId(saved.id)
      setHorseStatus(saved.profileStatus)
      setHorseDocumentUploadsPending(saved.id, pendingUploads.length > 0)
      await onSaved(saved)

      const readyUploads = pendingUploads.filter((item) => item.status === 'ready')
      let failedUploads = false
      for (const upload of readyUploads) {
        if (!await sendUpload(upload, saved.id)) failedUploads = true
      }
      const unresolved = pendingUploads.some((item) => item.status === 'invalid' || item.status === 'failed')
      if (failedUploads || unresolved) {
        setHorseDocumentUploadsPending(saved.id, true)
        setError(`Đã lưu hồ sơ nháp #${saved.id}, nhưng còn file chưa được lưu. Hãy sửa hoặc thử lại từng file bên dưới; hồ sơ chưa được gửi đăng ký.`)
        return
      }
      setHorseDocumentUploadsPending(saved.id, false)
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

  const existingClub = clubs.find((club) => club.id === form.clubId)
  const canDeleteDocuments = editing
    && (horseStatus === 'DRAFT' || horseStatus === 'REJECTED')

  if (loading) return <main className="page-content"><section className="panel" role="status">Đang tải hồ sơ ngựa...</section></main>
  if (routeEditing && loadError) return <main className="page-content"><section className="panel" role="alert"><h1>Không thể sửa hồ sơ</h1><p>{loadError}</p><Link className="button button-secondary" to="/owner/horses">Quay lại Ngựa của tôi</Link></section></main>

  return (
    <main className="page-content owner-horse-form-page">
      <nav className="breadcrumb" aria-label="Đường dẫn"><Link to="/owner/horses">Ngựa của tôi</Link><span aria-hidden="true">/</span>{editing ? 'Sửa hồ sơ' : 'Đăng ký ngựa'}</nav>
      <header className="page-heading"><div><p className="eyebrow">CHỦ SỞ HỮU NGỰA</p><h1>{editing ? 'Sửa hồ sơ ngựa' : 'Đăng ký ngựa'}</h1><p>{editing ? 'Lưu thay đổi vào hồ sơ nháp hoặc bị từ chối; việc gửi đăng ký được thực hiện riêng.' : 'Lưu hồ sơ nháp trước; sau đó kiểm tra và gửi đăng ký từ trang chi tiết.'}</p></div></header>
      <section className="panel form-panel owner-horse-form-panel">
        {loadError && <p className="error-message" role="alert">{loadError}</p>}
        {error && <p className="error-message" role="alert">{error}</p>}
        <form onSubmit={submit}>
          <div className="owner-horse-form-grid">
            <section className="owner-horse-card">
              <div className="section-title"><h2>Thông tin cơ bản</h2><p>Dấu * là thông tin bắt buộc theo hồ sơ hiện tại.</p></div>
              <div className="horse-form-grid">
                <label className="form-field"><span>Tên ngựa *</span><input required maxLength="100" value={form.name} aria-invalid={Boolean(fieldErrors.name)} onChange={(event) => setField('name', event.target.value)} />{fieldErrors.name && <small className="field-error" role="alert">{fieldErrors.name}</small>}</label>
                <label className="form-field"><span>Giống *</span><input required maxLength="100" value={form.breed} aria-invalid={Boolean(fieldErrors.breed)} onChange={(event) => setField('breed', event.target.value)} />{fieldErrors.breed && <small className="field-error" role="alert">{fieldErrors.breed}</small>}</label>
                <label className="form-field"><span>Ngày sinh *</span><input type="date" min={earliestDate} max={today} required value={form.dateOfBirth} aria-invalid={Boolean(fieldErrors.dateOfBirth)} onChange={(event) => setField('dateOfBirth', event.target.value)} />{fieldErrors.dateOfBirth && <small className="field-error" role="alert">{fieldErrors.dateOfBirth}</small>}</label>
                <label className="form-field"><span>Giới tính *</span><select required value={form.sex} aria-invalid={Boolean(fieldErrors.sex)} onChange={(event) => setField('sex', event.target.value)}><option value="">Chọn giới tính</option><option value="MALE">Đực</option><option value="FEMALE">Cái</option><option value="GELDING">Đực đã thiến</option></select>{fieldErrors.sex && <small className="field-error" role="alert">{fieldErrors.sex}</small>}</label>
                <label className="form-field"><span>Màu lông *</span><input required maxLength="50" value={form.coatColor} aria-invalid={Boolean(fieldErrors.coatColor)} onChange={(event) => setField('coatColor', event.target.value)} />{fieldErrors.coatColor && <small className="field-error" role="alert">{fieldErrors.coatColor}</small>}</label>
              </div>
            </section>

            <section className="owner-horse-card">
              <div className="section-title"><h2>Định danh và phả hệ</h2></div>
              <div className="horse-form-grid">
                <label className="form-field"><span>Số hộ chiếu / đăng ký *</span><input required minLength="5" maxLength="50" pattern="[A-Za-z0-9/-]+" value={form.registrationNumber} aria-invalid={Boolean(fieldErrors.registrationNumber)} onChange={(event) => setField('registrationNumber', event.target.value.toUpperCase())} />{fieldErrors.registrationNumber && <small className="field-error" role="alert">{fieldErrors.registrationNumber}</small>}</label>
                <label className="form-field"><span>Microchip *</span><input type="text" inputMode="numeric" autoComplete="off" maxLength="15" pattern="[0-9]{15}" required value={form.microchipNumber} aria-invalid={Boolean(fieldErrors.microchipNumber)} onChange={(event) => setField('microchipNumber', event.target.value)} /><small>Nhập đủ 15 chữ số; số 0 ở đầu được giữ nguyên.</small>{fieldErrors.microchipNumber && <small className="field-error" role="alert">{fieldErrors.microchipNumber}</small>}</label>
                <label className="form-field"><span>Tên ngựa cha *</span><input required maxLength="100" value={form.sireName} aria-invalid={Boolean(fieldErrors.sireName)} onChange={(event) => setField('sireName', event.target.value)} />{fieldErrors.sireName && <small className="field-error" role="alert">{fieldErrors.sireName}</small>}</label>
                <label className="form-field"><span>Tên ngựa mẹ *</span><input required maxLength="100" value={form.damName} aria-invalid={Boolean(fieldErrors.damName)} onChange={(event) => setField('damName', event.target.value)} />{fieldErrors.damName && <small className="field-error" role="alert">{fieldErrors.damName}</small>}</label>
              </div>
              <p className="form-help">Backend hiện chưa có trường lưu đặc điểm nhận dạng riêng.</p>
            </section>

            <section className="owner-horse-card">
              <div className="section-title"><h2>Chủ sở hữu và câu lạc bộ</h2></div>
              <div className="owner-account-summary">
                <div><span>Chủ sở hữu</span><strong>{currentUser.fullName || '—'}</strong></div>
                <div><span>Email</span><strong>{currentUser.email || '—'}</strong></div>
                <div><span>Điện thoại</span><strong>{currentUser.phone || '—'}</strong></div>
                <div><span>Địa chỉ</span><strong>{currentUser.address || '—'}</strong></div>
              </div>
              {editing ? (
                <div className="form-field"><span>Câu lạc bộ đã chọn</span><input readOnly value={existingClub?.name || (clubsLoading ? 'Đang tải...' : `CLB #${form.clubId}`)} /></div>
              ) : (
                <label className="form-field"><span>CLB muốn đăng ký *</span><select required value={form.clubId} disabled={clubsLoading || clubs.length === 0} aria-invalid={Boolean(fieldErrors.clubId)} onChange={(event) => setField('clubId', event.target.value)}><option value="">{clubsLoading ? 'Đang tải câu lạc bộ...' : 'Chọn câu lạc bộ'}</option>{clubs.map((club) => <option key={club.id} value={club.id}>{club.name}</option>)}</select>{fieldErrors.clubId && <small className="field-error" role="alert">{fieldErrors.clubId}</small>}</label>
              )}
              {!clubsLoading && clubs.length === 0 && <p className="error-message" role="alert">Không có câu lạc bộ đang hoạt động để đăng ký.</p>}
            </section>

            <section className="owner-horse-card">
              <div className="section-title"><h2>Hình ảnh ngựa</h2><p>Ảnh toàn thân trái/phải, mặt hoặc dấu hiệu nhận dạng giúp CLB đối chiếu. Không bắt buộc.</p></div>
              <label className="file-drop-area" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files, true) }}>
                <strong>Chọn hoặc thả ảnh vào đây</strong>
                <span>JPG, PNG hoặc WebP · tối đa 10 MB mỗi file theo cấu hình mặc định backend.</span>
                <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" multiple onChange={(event) => { addFiles(event.target.files, true); event.target.value = '' }} />
              </label>
              <p className="form-help">Ảnh được lưu cùng tài liệu đính kèm. Backend chưa có trường ảnh đại diện riêng nên chưa thể đặt ảnh đại diện.</p>
              {documentsError && <p className="error-message" role="alert">{documentsError}</p>}
              {pendingUploads.filter((item) => item.kind === 'image').map((item) => (
                <UploadRow key={item.key} item={item} onRetry={() => retryUpload(item)} onRemove={() => removeUpload(item.key)} busy={uploadBusy} />
              ))}
            </section>

            <section className="owner-horse-card">
              <div className="section-title"><h2>Giấy tờ đính kèm</h2><p>Loại giấy tờ phải thuộc danh sách hiện được backend chấp nhận.</p></div>
              <div className="horse-form-grid">
                <label className="form-field"><span>Loại giấy tờ</span><select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>{documentTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
                <label className="file-picker-button"><span>Chọn tài liệu</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" multiple onChange={(event) => { addFiles(event.target.files, false); event.target.value = '' }} /></label>
              </div>
              <p className="form-help">Nhận PDF và ảnh JPG/PNG/WebP, tối đa 10 MB mỗi file theo cấu hình mặc định backend. Chưa hỗ trợ ngày cấp, ngày hết hạn hoặc ghi chú.</p>
              <p className="form-help">Phả hệ, sổ tiêm phòng và hồ sơ khám/xét nghiệm chưa có loại riêng; chọn “Tài liệu khác” nếu cần đính kèm.</p>
              {pendingUploads.filter((item) => item.kind === 'document').map((item) => (
                <UploadRow key={item.key} item={item} onRetry={() => retryUpload(item)} onRemove={() => removeUpload(item.key)} busy={uploadBusy} />
              ))}
              {editing && (
                <>
                  {documentsError && <p className="error-message" role="alert">{documentsError}</p>}
                  <HorseDocuments
                    documents={documents}
                    onDelete={deleteDocument}
                    canDelete={(document) => canDeleteDocuments && String(document.uploadedById) === String(currentUser.id)}
                    deletingId={deletingId}
                  />
                </>
              )}
              {!editing && <p className="form-help">Tệp được chọn sẽ tải lên sau khi hồ sơ nháp được tạo.</p>}
            </section>

            <section className="owner-horse-card owner-health-unavailable">
              <div className="section-title"><h2>Thông tin sức khỏe</h2></div>
              <p>Backend hiện chưa có trường để Owner tự nhập thông tin sức khỏe. Nếu cần gửi hồ sơ khám/xét nghiệm, hãy đính kèm ở mục Giấy tờ với loại “Tài liệu khác”; kết luận khám do Vet thực hiện.</p>
            </section>
          </div>
          <div className="form-actions">
            <Link className="button button-secondary" to={editing ? `/owner/horses/${savedHorseId}` : '/owner/horses'}>Hủy</Link>
            <button className="button" type="submit" disabled={saving || uploadBusy || (!editing && (clubsLoading || clubs.length === 0))}>{saving ? 'Đang lưu...' : 'Lưu hồ sơ nháp'}</button>
          </div>
        </form>
      </section>
    </main>
  )
}

function UploadRow({ item, onRetry, onRemove, busy }) {
  const previewUrl = useMemo(
    () => item.kind === 'image' ? URL.createObjectURL(item.file) : '',
    [item.file, item.kind],
  )
  const statusLabels = {
    ready: 'Chưa tải lên',
    uploading: 'Đang tải lên...',
    saved: 'Đã lưu',
    failed: 'Tải lên thất bại',
    invalid: 'File không hợp lệ',
  }
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])
  return (
    <div className="pending-upload">
      {previewUrl && <img className="pending-upload-preview" src={previewUrl} alt={`Xem trước trên thiết bị: ${item.file.name}`} />}
      <div className="pending-upload-copy">
        <strong>{item.file.name}</strong>
        <span>{formatSize(item.file.size)} · {statusLabels[item.status]}</span>
        {item.kind === 'image' && item.status !== 'saved' && <small>Bản xem trước trên thiết bị; chưa phải ảnh đã lưu.</small>}
        {item.error && <small className="field-error" role="alert">{item.error}</small>}
      </div>
      <div className="pending-upload-actions">
        {item.status === 'failed' && <button className="button-secondary" type="button" disabled={busy} onClick={onRetry}>Thử lại file này</button>}
        {item.status !== 'uploading' && <button className="button-secondary" type="button" onClick={onRemove}>Bỏ file</button>}
      </div>
    </div>
  )
}

export default OwnerHorseForm
