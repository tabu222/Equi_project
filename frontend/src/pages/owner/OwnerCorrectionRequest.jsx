import { useEffect, useRef, useState } from 'react'
import { Link, useBlocker, useParams } from 'react-router-dom'
import { getChangeRequestOptions, getHorseById, getHorseDocuments, getProfileChangeRequests, submitProfileProposal, withdrawProfileProposal } from '../../api/horseApi.ts'
import HorseAvatar from '../../components/horse/HorseAvatar.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import ProfileProposalDetails, { ProtectedImage, ProposalFileButton } from '../../components/horse/ProfileProposalDetails.jsx'
import { displayProposalValue, documentTypeLabels, proposalFields, proposalStatusLabels, purposeLabels } from '../../components/horse/proposalLabels.js'
import './OwnerCorrectionRequest.css'

function fieldValue(horse, column) {
  const value = horse?.[proposalFields.find(([key]) => key === column)?.[2]] ?? ''
  return column === 'Gender' ? ({ MALE: 'Male', FEMALE: 'Female', GELDING: 'Gelding' })[value] || value : String(value)
}
function normalize(column, value) {
  const text = value.trim()
  return column === 'PassportNumber' ? text.toUpperCase() : column === 'MicrochipNumber' ? text.replaceAll(' ', '') : text
}
function today() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
function useUnsavedWarning(dirty) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty &&
    (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search))
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm('Bạn có thay đổi chưa gửi. Rời trang và bỏ các thay đổi này?')) blocker.proceed()
    else blocker.reset()
  }, [blocker])
  useEffect(() => {
    if (!dirty) return
    const beforeUnload = (event) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [dirty])
}

export default function OwnerCorrectionRequest({ horse: initialHorse, requests: initialRequests = [], onSubmitted }) {
  const { horseId } = useParams()
  const [horse, setHorse] = useState(initialHorse)
  const [documents, setDocuments] = useState([])
  const [options, setOptions] = useState(null)
  const [history, setHistory] = useState(initialRequests)
  const [rows, setRows] = useState([])
  const [files, setFiles] = useState([])
  const [avatarId, setAvatarId] = useState('')
  const [removeIds, setRemoveIds] = useState([])
  const [evidenceIds, setEvidenceIds] = useState([])
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [reload, setReload] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const urls = useRef(new Set())
  const nextId = useRef(0)
  const dirty = !!(rows.length || files.length || avatarId || removeIds.length || evidenceIds.length || reason)
  useUnsavedWarning(dirty)
  useEffect(() => {
    const created = urls.current
    return () => { created.forEach((url) => URL.revokeObjectURL(url)); created.clear() }
  }, [])
  useEffect(() => {
    let active = true
    Promise.all([getHorseById(horseId), getHorseDocuments(horseId), getChangeRequestOptions(horseId), getProfileChangeRequests(horseId)])
      .then(([freshHorse, docs, limits, requests]) => {
        if (active) { setHorse(freshHorse); setDocuments(docs); setOptions(limits); setHistory(requests); setError('') }
      }).catch((err) => { if (active) setError(err.message || 'Không tải được hồ sơ. Hãy thử lại.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [horseId, reload])

  const images = documents.filter((doc) => doc.isProfileImage && doc.isUploadedFile && doc.contentType?.startsWith('image/'))
  const currentAvatar = images.find((doc) => doc.isPrimary) || images[0]
  const pending = history.find((item) => item.status === 'Pending')
  const changes = rows.filter((row) => normalize(row.column, row.value) !== fieldValue(horse, row.column))
  const proposedAvatar = files.find((item) => item.Purpose === 'avatar')
  const selectedAvatar = images.find((doc) => doc.documentId === avatarId)
  const changeCount = changes.length + files.filter((item) => item.Purpose !== 'evidence').length + removeIds.length + (avatarId && avatarId !== currentAvatar?.documentId ? 1 : 0)
  const replaceable = documents.filter((doc) => doc.uploadedById === horse?.ownerUserId && !images.includes(doc) && !['Contract', 'Handover Record'].includes(doc.documentType))
  const errorText = (key) => errors[key] && <small className="correction-field-error" role="alert">{[].concat(errors[key]).join(' ')}</small>
  function updateRow(index, patch) {
    setRows((current) => current.map((row, i) => i === index ? { ...row, ...patch } : row)); setErrors({}); setSuccess('')
  }
  function updateFile(id, patch) { setFiles((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item)); setErrors({}) }
  function discardFile(id) {
    const item = files.find((file) => file.id === id)
    if (item?.preview) { URL.revokeObjectURL(item.preview); urls.current.delete(item.preview) }
    setFiles((current) => current.filter((file) => file.id !== id))
  }
  function addFiles(event, purpose) {
    const selected = Array.from(event.target.files || [])
    event.target.value = ''
    if (!options) return
    if (selected.length + files.length > options.MaxFiles) { setError(`Tối đa ${options.MaxFiles} file trong một yêu cầu.`); return }
    const added = selected.map((file) => {
      const image = /\.(jpe?g|png|webp)$/i.test(file.name)
      const allowed = ['image', 'avatar'].includes(purpose) ? image : /\.(pdf|jpe?g|png)$/i.test(file.name)
      const fileError = !allowed ? 'Định dạng file không được hỗ trợ.' : !file.size ? 'File rỗng.' : file.size > options.MaxFileMB * 1024 * 1024 ? `File vượt quá ${options.MaxFileMB} MB.` : ''
      const preview = image && !fileError ? URL.createObjectURL(file) : ''
      if (preview) urls.current.add(preview)
      return { id: ++nextId.current, file, Purpose: purpose, DocumentName: file.name.slice(0, 150), DocumentType: 'Other', Note: '', preview, error: fileError }
    })
    if (purpose === 'avatar') {
      files.filter((item) => item.Purpose === 'avatar').forEach((item) => discardFile(item.id))
      setAvatarId('')
      setFiles((current) => [...current.filter((item) => item.Purpose !== 'avatar'), ...added.slice(0, 1)])
    } else setFiles((current) => [...current, ...added])
    setError(''); setSuccess('')
  }
  function toggleId(setter, id) { setter((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]); setErrors({}) }
  function clearForm() {
    urls.current.forEach((url) => URL.revokeObjectURL(url)); urls.current.clear()
    setRows([]); setFiles([]); setAvatarId(''); setRemoveIds([]); setEvidenceIds([]); setReason(''); setErrors({})
  }
  async function submit(event) {
    event.preventDefault()
    if (submitting) return
    const nextErrors = {}
    rows.forEach((row) => {
      const value = normalize(row.column, row.value)
      if (!value) nextErrors[row.column] = 'Cần nhập giá trị đề nghị; trường này không cho phép xóa.'
      if (row.column === 'DateOfBirth' && row.value > today()) nextErrors[row.column] = 'Ngày sinh không được ở tương lai.'
      if (row.column === 'DateOfBirth' && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number(value.slice(0, 4)) < new Date().getFullYear() - 40)) nextErrors[row.column] = 'Ngày sinh không hợp lệ hoặc quá 40 năm.'
      if (row.column === 'MicrochipNumber' && !/^\d{15}$/.test(value)) nextErrors[row.column] = 'Microchip phải gồm đúng 15 chữ số.'
      if (row.column === 'PassportNumber' && !/^[A-Z0-9][A-Z0-9/-]{4,49}$/.test(value)) nextErrors[row.column] = 'Hộ chiếu gồm 5–50 ký tự: chữ, số, dấu / hoặc -.'
    })
    if (!reason.trim()) nextErrors.Reason = 'Cần nhập lý do chung cho yêu cầu.'
    files.forEach((item, index) => {
      if (item.error) nextErrors[`file${index}`] = item.error
      if (item.Purpose === 'replace' && !item.ReplacesDocumentID) nextErrors[`file${index}`] = 'Cần chọn tài liệu hiện tại.'
      if (!item.DocumentName.trim()) nextErrors[`file${index}`] = 'Cần nhập tên hiển thị của tài liệu.'
    })
    if (!changeCount) nextErrors.Changes = 'Cần có ít nhất một thay đổi thực sự.'
    if (currentAvatar && removeIds.includes(currentAvatar.documentId) && !avatarId && !proposedAvatar) nextErrors.AvatarDocumentID = 'Chọn ảnh đại diện thay thế trước khi gỡ ảnh hiện tại.'
    setErrors(nextErrors); setError(''); setSuccess('')
    if (Object.keys(nextErrors).length) return
    setSubmitting(true)
    try {
      const saved = await submitProfileProposal(horseId, {
        Changes: Object.fromEntries(changes.map((row) => [row.column, normalize(row.column, row.value)])),
        Reason: reason.trim(), RemoveImageIDs: removeIds.map(Number), EvidenceDocumentIDs: evidenceIds.map(Number),
        ...(avatarId ? { AvatarDocumentID: Number(avatarId) } : {}),
      }, files.map(({ file, Purpose, DocumentName, DocumentType, Note, ReplacesDocumentID }) => ({ file, Purpose, DocumentName, DocumentType, Note, ...(ReplacesDocumentID ? { ReplacesDocumentID } : {}) })))
      setHistory((current) => [saved, ...current]); clearForm()
      setSuccess(`Yêu cầu #${saved.requestId} · Chờ duyệt. Hồ sơ hiện tại được giữ nguyên cho đến khi Manager duyệt.`)
      onSubmitted?.(saved)
    } catch (err) {
      setError(err.message || 'Không gửi được yêu cầu. Nội dung được giữ lại để thử lại.'); setErrors(err.fieldErrors || {})
      if (err.code === 'PENDING_REQUEST_EXISTS') {
        try { setHistory(await getProfileChangeRequests(horseId)) } catch { /* Retain the original error and selected files. */ }
      }
    } finally { setSubmitting(false) }
  }
  async function reuseRejected(request) {
    if (dirty && !window.confirm('Thay nội dung đang soạn bằng yêu cầu bị từ chối?')) return
    try {
      const [freshHorse, docs, requests] = await Promise.all([getHorseById(horseId), getHorseDocuments(horseId), getProfileChangeRequests(horseId)])
      clearForm(); setHorse(freshHorse); setDocuments(docs); setHistory(requests)
      setRows(request.changes.filter((item) => proposalFields.some(([key]) => key === item.Field)).map((item) => ({ column: item.Field, value: item.NewValue || '' })))
      setReason(request.reason); setSuccess('Đã đọc lại hồ sơ hiện tại. Kiểm tra các giá trị và chọn lại ảnh / file cần gửi trong yêu cầu mới.')
    } catch (err) { setError(err.message) }
  }
  async function withdrawRequest(request) {
    if (!window.confirm(`Rút yêu cầu #${request.requestId}? Hồ sơ hiện tại sẽ được giữ nguyên.`)) return
    setSubmitting(true); setError('')
    try {
      const saved = await withdrawProfileProposal(request.requestId)
      setHistory((current) => current.map((item) => item.requestId === saved.requestId ? saved : item))
      setSuccess(`Đã rút yêu cầu #${saved.requestId}. Bạn có thể tạo yêu cầu mới.`)
    } catch (err) { setError(err.message) }
    finally { setSubmitting(false) }
  }

  if (loading) return <section className="correction-page panel" role="status">Đang tải hồ sơ và danh mục tài liệu…</section>
  if (!horse || !options) return <section className="correction-page panel" role="alert"><p>{error || 'Không tìm thấy hồ sơ ngựa.'}</p><button className="button" onClick={() => { setLoading(true); setReload((n) => n + 1) }}>Thử lại</button></section>
  return <section className="page-content correction-page">
    <Link className="correction-page__back" to={`/owner/horses/${horseId}`}>← Hồ sơ ngựa / {horse.name}</Link>
    <header className="correction-page__header"><div><p className="correction-page__eyebrow">HỒ SƠ NGỰA</p><h1>Yêu cầu cập nhật hồ sơ</h1><p className="correction-page__subtitle">Chọn thông tin muốn thay đổi. Hồ sơ hiện tại được giữ nguyên cho đến khi yêu cầu được duyệt.</p></div></header>
    <div className="correction-identity panel"><HorseAvatar horseId={horseId} documents={documents} name={horse.name} /><div><h2>{horse.name}</h2><p>Mã ngựa: {horse.code || 'Chưa cấp mã'}</p></div><StatusBadge status={horse.profileStatus} type="registration" /></div>
    {horse.profileStatus !== 'APPROVED' && <p className="correction-page__notice">Chỉ đề nghị cập nhật hồ sơ đã tiếp nhận. Hồ sơ nháp / bị từ chối sử dụng luồng chỉnh sửa hiện có.</p>}
    {pending && <p className="correction-page__notice">Mỗi ngựa chỉ có một yêu cầu chờ duyệt. <a href={`#request-${pending.requestId}`}>Xem yêu cầu #{pending.requestId}</a>.</p>}
    {error && <p className="correction-page__error" role="alert">{error}</p>}{success && <p className="correction-page__success" role="status">{success}</p>}
    <form className="correction-form" onSubmit={submit} noValidate><fieldset disabled={submitting || !!pending || horse.profileStatus !== 'APPROVED'}>
      <details className="correction-section" open><summary><span>A. Thông tin hồ sơ</span><span>{changes.length} thay đổi</span></summary><div className="correction-section-body">
        <p className="correction-help">Chỉ thêm thông tin cần sửa. Microchip và hộ chiếu cần Manager đối chiếu trước khi đính chính.</p>
        {rows.map((row, index) => <div className="correction-row" key={index}>
          <label>Thông tin cần sửa<select value={row.column} onChange={(event) => updateRow(index, { column: event.target.value, value: '' })}>{proposalFields.map(([key, label]) => <option key={key} value={key} disabled={rows.some((other, i) => i !== index && other.column === key)}>{label}</option>)}</select></label>
          <label>Giá trị hiện tại<input readOnly value={displayProposalValue(fieldValue(horse, row.column))} /></label>
          <label>Giá trị đề nghị{row.column === 'Gender' ? <select required value={row.value} onChange={(event) => updateRow(index, { value: event.target.value })}><option value="">Chọn giới tính</option><option value="Male">Đực</option><option value="Female">Cái</option><option value="Gelding">Đực đã thiến</option></select> : <input required type={row.column === 'DateOfBirth' ? 'date' : 'text'} max={row.column === 'DateOfBirth' ? today() : undefined} maxLength={proposalFields.find(([key]) => key === row.column)?.[3]} value={row.value} onChange={(event) => updateRow(index, { value: event.target.value })} aria-invalid={!!errors[row.column]} />}{errorText(row.column)}</label>
          <button type="button" className="button button-secondary" aria-label={`Bỏ dòng ${index + 1}`} onClick={() => setRows((current) => current.filter((_, i) => i !== index))}>Bỏ dòng</button>
        </div>)}
        <button type="button" className="button button-secondary" disabled={rows.length === proposalFields.length} onClick={() => setRows((current) => [...current, { column: proposalFields.find(([key]) => !current.some((row) => row.column === key))[0], value: '' }])}>＋ Thêm thông tin cần sửa</button>{errorText('Changes')}
      </div></details>
      <details className="correction-section" open><summary><span>B. Hình ảnh</span><span>{files.filter((item) => ['image', 'avatar'].includes(item.Purpose)).length + removeIds.length + (avatarId ? 1 : 0)} thay đổi</span></summary><div className="correction-section-body">
        <div className="proposal-comparison"><div><h3>Ảnh đại diện hiện tại</h3>{currentAvatar ? <ProtectedImage fileUrl={currentAvatar.fileUrl} name={horse.name} /> : <p>Chưa có ảnh đại diện</p>}</div><div><h3>Ảnh đại diện đề nghị</h3>{proposedAvatar?.preview ? <img className="proposal-image" src={proposedAvatar.preview} alt="Ảnh đại diện đề nghị" /> : selectedAvatar ? <ProtectedImage fileUrl={selectedAvatar.fileUrl} name={selectedAvatar.documentName} /> : <p>Giữ ảnh đại diện hiện tại</p>}
          <label className="correction-upload">Chọn ảnh đại diện từ máy<input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={(event) => addFiles(event, 'avatar')} /></label>{avatarId && <button className="button button-secondary" type="button" onClick={() => setAvatarId('')}>Bỏ ảnh đại diện đề nghị</button>}
        </div></div>{errorText('AvatarDocumentID')}
        <p className="correction-help">JPG, PNG, WebP · tối đa {options.MaxFileMB} MB/file. Chọn ảnh trong thư viện hoặc tải ảnh mới; tất cả đều chờ duyệt.</p>
        <div className="correction-gallery">{images.map((doc) => <article className="proposal-file" key={doc.documentId}><ProtectedImage fileUrl={doc.fileUrl} name={doc.documentName} /><strong>{doc.documentName}</strong>{doc.documentId === currentAvatar?.documentId && <small>Ảnh đại diện hiện tại</small>}
          <label className="correction-check"><input type="radio" name="galleryAvatar" checked={avatarId === doc.documentId} disabled={removeIds.includes(doc.documentId) || doc.documentId === currentAvatar?.documentId} onChange={() => { files.filter((item) => item.Purpose === 'avatar').forEach((item) => discardFile(item.id)); setAvatarId(doc.documentId) }} />Đề nghị làm ảnh đại diện</label>
          {doc.uploadedById === horse.ownerUserId && <label className="correction-check"><input type="checkbox" checked={removeIds.includes(doc.documentId)} disabled={avatarId === doc.documentId || evidenceIds.includes(doc.documentId)} onChange={() => toggleId(setRemoveIds, doc.documentId)} />Đề nghị gỡ ảnh</label>}<ProposalFileButton fileUrl={doc.fileUrl} name={doc.documentName} />
        </article>)}</div><label className="correction-upload">Bổ sung ảnh vào hồ sơ<input type="file" accept=".jpg,.jpeg,.png,.webp" multiple onChange={(event) => addFiles(event, 'image')} /></label>
      </div></details>
      <details className="correction-section" open><summary><span>C. Tài liệu</span><span>{files.filter((item) => !['image', 'avatar'].includes(item.Purpose)).length + evidenceIds.length} mục</span></summary><div className="correction-section-body">
        <p className="correction-help">PDF, JPG, PNG · tối đa {options.MaxFileMB} MB/file, {options.MaxFiles} file/yêu cầu (gồm ảnh). Thông tin sức khỏe do Owner cung cấp là tài liệu bổ sung để chuyên môn xem xét.</p>
        <details className="correction-existing-documents"><summary>Chọn tài liệu trong hồ sơ làm minh chứng</summary>{documents.length ? documents.map((doc) => <label className="correction-check" key={doc.documentId}><input type="checkbox" disabled={removeIds.includes(doc.documentId)} checked={evidenceIds.includes(doc.documentId)} onChange={() => toggleId(setEvidenceIds, doc.documentId)} />{doc.documentName} · {documentTypeLabels[doc.documentType]}</label>) : <p>Chưa có tài liệu trong hồ sơ.</p>}</details>
        <label className="correction-upload">Tải tài liệu lên<input type="file" accept=".pdf,.jpg,.jpeg,.png" multiple onChange={(event) => addFiles(event, 'evidence')} /></label>{errorText('Documents')}{errorText('Attachments')}
      </div></details>
      {files.length > 0 && <section className="correction-section"><div className="correction-section-body"><h2>Tệp đã chọn ({files.length}/{options.MaxFiles})</h2><div className="correction-file-list">{files.map((item, index) => <article className="proposal-file" key={item.id}>
        <div className="correction-file-heading"><strong>{purposeLabels[item.Purpose]}</strong><button type="button" className="button button-secondary" onClick={() => discardFile(item.id)}>Bỏ chọn</button></div>
        {item.preview && <a href={item.preview} target="_blank" rel="noreferrer" aria-label={`Xem lớn ${item.file.name}`}><img className="proposal-image" src={item.preview} alt={item.file.name} /><span>Xem lớn</span></a>}
        <p>{item.file.name} · {(item.file.size / 1024).toFixed(1)} KB · {item.file.type || 'Không xác định'}</p><p role="status">{item.error ? 'File lỗi — cần bỏ chọn' : submitting ? 'Đang tải cùng yêu cầu…' : 'Đã chọn · sẽ tải khi gửi yêu cầu'}</p>
        {item.error && <small className="correction-field-error">{item.error}</small>}{errorText(`file${index}`)}
        {!['image', 'avatar'].includes(item.Purpose) && <div className="correction-doc-fields">
          <label>Mục đích<select value={item.Purpose} onChange={(event) => updateFile(item.id, { Purpose: event.target.value, ReplacesDocumentID: undefined })}><option value="evidence">Minh chứng cho yêu cầu sửa</option><option value="add">Bổ sung tài liệu vào hồ sơ</option><option value="replace">Thay thế bằng phiên bản mới</option></select></label>
          <label>Tên hiển thị<input required maxLength={150} value={item.DocumentName} onChange={(event) => updateFile(item.id, { DocumentName: event.target.value })} /></label>
          <label>Loại tài liệu<select disabled={item.Purpose === 'replace'} value={item.DocumentType} onChange={(event) => updateFile(item.id, { DocumentType: event.target.value })}>{options.DocumentTypes.map((type) => <option key={type} value={type}>{documentTypeLabels[type] || type}</option>)}</select></label>
          {item.Purpose === 'replace' && <label>Tài liệu hiện tại<select required value={item.ReplacesDocumentID || ''} onChange={(event) => { const doc = replaceable.find((d) => Number(d.documentId) === Number(event.target.value)); updateFile(item.id, { ReplacesDocumentID: doc ? Number(doc.documentId) : undefined, DocumentType: doc?.documentType || 'Other' }) }}><option value="">Chọn tài liệu được phép thay thế</option>{replaceable.map((doc) => <option key={doc.documentId} value={doc.documentId} disabled={files.some((other) => other.id !== item.id && other.ReplacesDocumentID === Number(doc.documentId)) || evidenceIds.includes(doc.documentId)}>{doc.documentName}</option>)}</select>{item.ReplacesDocumentID && <ProposalFileButton fileUrl={replaceable.find((doc) => Number(doc.documentId) === item.ReplacesDocumentID)?.fileUrl} name="Tài liệu hiện tại" />}<small>Phiên bản đề nghị: {item.file.name}. File cũ được giữ trong lịch sử.</small></label>}
          <label>Ghi chú {item.Purpose === 'replace' ? 'nội dung đã chỉnh sửa' : '(tùy chọn)'}<textarea rows={2} maxLength={1000} value={item.Note} onChange={(event) => updateFile(item.id, { Note: event.target.value })} /></label>
        </div>}
      </article>)}</div></div></section>}
      <details className="correction-section" open><summary><span>D. Lý do và kiểm tra thay đổi</span><span>{changeCount} thay đổi</span></summary><div className="correction-section-body">
        <label>Lý do chung *<textarea required rows={3} maxLength={1000} value={reason} aria-invalid={!!errors.Reason} onChange={(event) => { setReason(event.target.value); setErrors((current) => ({ ...current, Reason: undefined })) }} placeholder="Tên ngựa bị nhập sai khi đăng ký; đề nghị sửa theo giấy chứng nhận đính kèm." />{errorText('Reason')}</label>
        <h3>Kiểm tra trước khi gửi</h3>{changes.map((row) => <p key={row.column}><strong>{proposalFields.find(([key]) => key === row.column)?.[1]}:</strong> {displayProposalValue(fieldValue(horse, row.column))} → {displayProposalValue(normalize(row.column, row.value))}</p>)}
        {rows.length > changes.length && <p className="correction-help">Các giá trị giống hiện tại sẽ không được gửi.</p>}
        <p>Ảnh đại diện đề nghị: {proposedAvatar?.file.name || selectedAvatar?.documentName || 'Giữ nguyên'}</p><p>Ảnh bổ sung: {files.filter((item) => item.Purpose === 'image').length} · Ảnh đề nghị gỡ: {removeIds.length}</p>
        {files.filter((item) => !['image', 'avatar'].includes(item.Purpose)).map((item) => <p key={item.id}>{purposeLabels[item.Purpose]}: {item.DocumentName}{item.ReplacesDocumentID ? ` ← ${replaceable.find((doc) => Number(doc.documentId) === item.ReplacesDocumentID)?.documentName || ''}` : ''}</p>)}<p>Minh chứng trong hồ sơ: {evidenceIds.length}</p>{errorText('Changes')}
      </div></details>
      <div className="correction-form__actions"><Link to={`/owner/horses/${horseId}`}>Hủy</Link><button className="button" type="submit" disabled={submitting || !changeCount || files.some((item) => item.error)}>{submitting ? 'Đang gửi…' : 'Gửi yêu cầu duyệt'}</button></div>
    </fieldset></form>
    <section className="correction-history correction-section"><div className="correction-section-body"><h2>Lịch sử yêu cầu ({history.length})</h2>{history.length === 0 ? <p>Chưa có yêu cầu cập nhật hồ sơ.</p> : history.map((request) => <article className="correction-history__item" id={`request-${request.requestId}`} key={request.requestId}>
      <details><summary><strong>Yêu cầu #{request.requestId}</strong><span className="correction-history__status">{proposalStatusLabels[request.status] || request.status}</span></summary><p>Gửi lúc {new Date(request.createdAt).toLocaleString('vi-VN')}</p><ProfileProposalDetails request={request} />{request.status === 'Rejected' && !pending && <button type="button" className="button button-secondary" disabled={submitting} onClick={() => void reuseRejected(request)}>Tạo yêu cầu mới từ yêu cầu bị từ chối</button>}</details>
      <p>{request.changes.length} trường · {request.attachments.length} tệp · {request.removedImages.length} ảnh gỡ{request.avatarDocument ? ' · Thay ảnh đại diện' : ''}</p>
      {request.status === 'Pending' && <button className="button button-secondary" type="button" disabled={submitting} onClick={() => void withdrawRequest(request)}>{submitting ? 'Đang xử lý…' : 'Rút yêu cầu'}</button>}
    </article>)}</div></section>
  </section>
}
