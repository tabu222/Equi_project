import { useEffect, useState } from 'react'
import { getProposalFile } from '../../api/horseApi.ts'

import { displayProposalValue, documentTypeLabels, proposalFields, purposeLabels } from './proposalLabels.js'

export function ProtectedImage({ fileUrl, name }) {
  const [loaded, setLoaded] = useState({ source: '', url: '', failed: false })
  useEffect(() => {
    let active = true
    let localUrl = ''
    getProposalFile(fileUrl).then((blob) => {
      if (!active) return
      localUrl = URL.createObjectURL(blob)
      setLoaded({ source: fileUrl, url: localUrl, failed: false })
    }).catch(() => { if (active) setLoaded({ source: fileUrl, url: '', failed: true }) })
    return () => { active = false; if (localUrl) URL.revokeObjectURL(localUrl) }
  }, [fileUrl])
  const current = loaded.source === fileUrl ? loaded : { url: '', failed: false }
  return current.url ? <img className="proposal-image" src={current.url} alt={name} /> : <span>{current.failed ? 'Không tải được ảnh' : 'Đang tải ảnh…'}</span>
}

export function ProposalFileButton({ fileUrl, name, download = false }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function openFile() {
    setBusy(true); setError('')
    // Create the viewing window in the click event so popup blockers do not discard it.
    const preview = download ? null : window.open('', '_blank')
    if (preview) preview.opener = null
    try {
      const blob = await getProposalFile(fileUrl, download)
      const url = URL.createObjectURL(blob)
      if (download || !preview) {
        const anchor = document.createElement('a')
        anchor.href = url; anchor.download = name; anchor.click()
      } else preview.location.href = url
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (err) { preview?.close(); setError(err.message || 'Không tải được file.') }
    finally { setBusy(false) }
  }
  return <><button className="button button-secondary" type="button" disabled={busy} onClick={() => void openFile()}>{busy ? 'Đang tải…' : download ? 'Tải file' : 'Xem file'}</button>{error && <small role="alert">{error}</small>}</>
}

function ExistingDocument({ item }) {
  if (!item) return null
  const externalUrl = /^https?:\/\//i.test(item.FileUrl || '') ? item.FileUrl : ''
  return <span>{item.DocumentName} {item.IsUploadedFile ? <ProposalFileButton fileUrl={item.FileUrl} name={item.DocumentName} /> : externalUrl && <a href={externalUrl} target="_blank" rel="noreferrer">Mở liên kết tài liệu</a>}</span>
}

export default function ProfileProposalDetails({ request }) {
  return <div className="proposal-details">
    {request.changes.length > 0 && <div className="proposal-table-wrap"><table className="proposal-table"><thead><tr><th>Thông tin</th><th>Hiện tại khi gửi</th><th>Giá trị đề nghị</th></tr></thead><tbody>
      {request.changes.map((item) => <tr key={item.Field}><th>{proposalFields.find(([key]) => key === item.Field)?.[1] || item.Field}</th><td>{displayProposalValue(item.OldValue)}</td><td>{displayProposalValue(item.NewValue)}</td></tr>)}
    </tbody></table></div>}
    {(request.avatarDocument || request.attachments.some((i) => i.Purpose === 'avatar')) && <div className="proposal-comparison">
      <div><strong>Ảnh đại diện hiện tại khi gửi</strong>{request.currentAvatar ? <ProtectedImage fileUrl={request.currentAvatar.FileUrl} name={request.currentAvatar.DocumentName} /> : <p>Chưa có ảnh</p>}</div>
      <div><strong>Ảnh đại diện đề nghị</strong><ProtectedImage fileUrl={request.avatarDocument?.FileUrl || request.attachments.find((i) => i.Purpose === 'avatar')?.FileUrl} name="Ảnh đại diện đề nghị" /></div>
    </div>}
    <div className="proposal-attachment-grid">{request.attachments.map((item, index) => <article className="proposal-file" key={index}>
      <strong>{purposeLabels[item.Purpose]} · {item.DocumentName}</strong>
      <p>{documentTypeLabels[item.DocumentType] || item.DocumentType} · {((item.Size || 0) / 1024).toFixed(1)} KB</p>
      {item.Purpose === 'image' && <ProtectedImage fileUrl={item.FileUrl} name={item.DocumentName} />}
      {item.CurrentDocument && <p>Tài liệu hiện tại: <ExistingDocument item={item.CurrentDocument} /></p>}
      {item.Note && <p>Nội dung chỉnh sửa / ghi chú: {item.Note}</p>}
      <ProposalFileButton fileUrl={item.FileUrl} name={item.OriginalName || item.DocumentName} />{' '}
      <ProposalFileButton fileUrl={item.FileUrl} name={item.OriginalName || item.DocumentName} download />
    </article>)}</div>
    {request.removedImages.map((item) => <p key={item.DocumentID}>Đề nghị gỡ ảnh: <ExistingDocument item={item} /></p>)}
    {request.evidenceDocuments.map((item) => <p key={item.DocumentID}>Minh chứng trong hồ sơ: <ExistingDocument item={item} /></p>)}
    <p><strong>Lý do:</strong> {request.reason}</p>
    {request.reviewedAt && <p>Xử lý: {new Date(request.reviewedAt).toLocaleString('vi-VN')} · {request.reviewedByName || 'Manager'}</p>}
    {request.rejectionReason && <p><strong>Phản hồi:</strong> {request.rejectionReason}</p>}
  </div>
}
