import { useEffect, useState } from 'react'
import { resolveFileUrl } from '../../api/apiClient.ts'
import { getHorseDocumentFile } from '../../api/horseApi.ts'
import EmptyState from '../common/EmptyState.jsx'
import { formatHorseDateTime } from './horseDisplay.js'

const noDocuments = []
const documentTypeLabels = {
  Passport: 'Hộ chiếu / giấy đăng ký ngựa',
  'Microchip Certificate': 'Chứng nhận microchip',
  'Ownership Proof': 'Chứng minh sở hữu',
  'Handover Record': 'Biên bản bàn giao',
  Contract: 'Hợp đồng',
  Other: 'Tài liệu khác / ảnh ngựa',
}

function HorseDocuments({ documents = noDocuments, onDelete, canDelete = false, deletingId = '' }) {
  const availableDocuments = Array.isArray(documents) ? documents : noDocuments
  const imageDocuments = availableDocuments.filter(
    (document) => document.isProfileImage !== false && document.isUploadedFile && document.contentType?.startsWith('image/'),
  )
  const fileDocuments = availableDocuments.filter((document) => !imageDocuments.includes(document))
  const [imageUrls, setImageUrls] = useState({})
  const [previewErrors, setPreviewErrors] = useState({})
  const [fileError, setFileError] = useState('')

  useEffect(() => {
    let active = true
    const createdUrls = []
    const imageFiles = availableDocuments.filter(
      (document) => document.isProfileImage !== false && document.isUploadedFile && document.contentType?.startsWith('image/'),
    )

    Promise.all(imageFiles.map(async (document) => {
      try {
        const blob = await getHorseDocumentFile(document.documentId)
        const url = URL.createObjectURL(blob)
        if (!active) {
          URL.revokeObjectURL(url)
          return [document.documentId, '']
        }
        createdUrls.push(url)
        return [document.documentId, url]
      } catch (error) {
        return [document.documentId, '', error instanceof Error ? error.message : 'Không thể tải ảnh xem trước.']
      }
    })).then((entries) => {
      if (active) {
        setImageUrls(Object.fromEntries(entries.map(([id, url]) => [id, url])))
        setPreviewErrors(Object.fromEntries(
          entries.filter(([, , error]) => error).map(([id, , error]) => [id, error]),
        ))
      }
    })

    return () => {
      active = false
      createdUrls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [availableDocuments])

  async function openFile(document) {
    setFileError('')
    const openedWindow = window.open('about:blank', '_blank')
    try {
      const blob = await getHorseDocumentFile(document.documentId)
      const url = URL.createObjectURL(blob)
      if (openedWindow) {
        openedWindow.opener = null
        openedWindow.location.href = url
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      } else {
        const link = window.document.createElement('a')
        link.href = url
        link.download = document.documentName
        link.click()
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      }
    } catch (error) {
      openedWindow?.close()
      setFileError(error instanceof Error ? error.message : 'Không thể mở tài liệu.')
    }
  }

  async function downloadFile(document) {
    setFileError('')
    try {
      const blob = await getHorseDocumentFile(document.documentId, true)
      const url = URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = url
      link.download = document.documentName
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (error) {
      setFileError(error instanceof Error ? error.message : 'Không thể tải tài liệu.')
    }
  }

  return (
    <div className="horse-media-library">
      {fileError && <p className="error-message" role="alert">{fileError}</p>}
      <section className="profile-section profile-info-card">
        <div className="section-title"><h2>Thư viện ảnh</h2></div>
        {imageDocuments.length === 0 ? (
          <EmptyState title="Chưa có ảnh" description="Ảnh ngựa được tải lên sẽ hiển thị tại đây." />
        ) : (
          <div className="horse-image-gallery">
            {imageDocuments.map((document) => (
              <figure className="horse-gallery-item" key={document.documentId}>
                {imageUrls[document.documentId] ? (
                  <a href={imageUrls[document.documentId]} target="_blank" rel="noreferrer" aria-label={`Mở ảnh ${document.documentName} kích thước đầy đủ`}>
                    <img src={imageUrls[document.documentId]} alt={document.documentName} />
                  </a>
                ) : (
                  <div className="horse-gallery-placeholder" role="status">
                    {previewErrors[document.documentId] ? 'Không tải được ảnh' : 'Đang tải ảnh...'}
                  </div>
                )}
                <figcaption>{document.documentName}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </section>
      <section className="profile-section profile-info-card">
        <div className="section-title"><h2>Tài liệu</h2></div>
        {fileDocuments.length === 0 ? (
          <EmptyState title="Chưa có tài liệu" description="Tài liệu hồ sơ được cung cấp sẽ hiển thị tại đây." />
        ) : (
          <div className="document-list">
            {fileDocuments.map((document) => {
            let externalUrl = ''
            let externalUrlError = ''
            if (!document.isUploadedFile && document.fileUrl) {
              try {
                externalUrl = resolveFileUrl(document.fileUrl)
              } catch (error) {
                externalUrlError = error instanceof Error ? error.message : 'Liên kết tài liệu không hợp lệ.'
              }
            }
            return (
              <article className="document-item" key={document.documentId}>
              <div className="document-copy">
                <strong>{document.documentName}</strong>
                <span>{documentTypeLabels[document.documentType] || document.documentType}{document.uploadedAt ? ` · ${formatHorseDateTime(document.uploadedAt)}` : ''}</span>
                <span>{document.isUploadedFile ? 'Đã lưu trên máy chủ' : 'Liên kết tài liệu'}</span>
                {previewErrors[document.documentId] && <span role="status">Không tải được ảnh xem trước: {previewErrors[document.documentId]}</span>}
                {externalUrlError && <span role="alert">{externalUrlError}</span>}
              </div>
              <div className="document-actions">
                {document.isUploadedFile ? (
                  <>
                    <button className="button-secondary" type="button" onClick={() => openFile(document)}>Xem</button>
                    <button className="button-secondary" type="button" onClick={() => downloadFile(document)}>Tải xuống</button>
                  </>
                ) : externalUrl ? (
                  <a href={externalUrl} target="_blank" rel="noreferrer">Mở liên kết</a>
                ) : <span>Không có tệp</span>}
                {(typeof canDelete === 'function' ? canDelete(document) : canDelete) && onDelete && (
                  <button
                    className="button-secondary document-delete"
                    type="button"
                    disabled={deletingId === document.documentId}
                    onClick={() => {
                      if (window.confirm(`Bạn có chắc muốn xóa “${document.documentName}” không?`)) {
                        onDelete(document)
                      }
                    }}
                  >
                    {deletingId === document.documentId ? 'Đang xóa...' : 'Xóa'}
                  </button>
                )}
              </div>
            </article>
            )
            })}
          </div>
        )}
      </section>
    </div>
  )
}

export default HorseDocuments
