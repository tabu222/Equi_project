import EmptyState from '../common/EmptyState.jsx'

function HorseDocuments({ documents = [] }) {
  const availableDocuments = Array.isArray(documents) ? documents : []

  return (
    <section className="profile-section">
      <div className="section-title"><h2>Tài liệu</h2></div>
      {availableDocuments.length === 0 ? <EmptyState title="Chưa có tài liệu" description="Hiện chưa có tài liệu nào được cung cấp cho hồ sơ ngựa này." /> : (
        <div className="document-list">
          {availableDocuments.map((document) => (
            <div className="document-item" key={document.documentId}>
              <div><strong>{document.documentName}</strong><span>{document.documentType} · {document.uploadedAt}</span></div>
              {document.fileUrl && <a href={document.fileUrl} target="_blank" rel="noreferrer">Xem tài liệu</a>}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default HorseDocuments
