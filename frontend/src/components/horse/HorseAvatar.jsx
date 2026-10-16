import { useEffect, useState } from 'react'
import { getHorseDocumentFile, getHorseDocuments } from '../../api/horseApi.ts'

function findImageDocument(documents) {
  const images = documents.filter((document) => !document.isRetired && document.isProfileImage !== false && document.isUploadedFile && document.contentType?.startsWith('image/'))
  return images.find((document) => document.isPrimary) || images[0]
}

function HorseAvatar({ horseId, documents, name, size = 'regular' }) {
  const [imageUrl, setImageUrl] = useState('')
  const [imageUnavailable, setImageUnavailable] = useState(false)
  const [imageLoading, setImageLoading] = useState(true)

  useEffect(() => {
    let active = true
    let objectUrl = ''

    async function loadImage() {
      setImageUrl('')
      setImageUnavailable(false)
      setImageLoading(true)
      try {
        const availableDocuments = documents || await getHorseDocuments(String(horseId))
        const imageDocument = findImageDocument(availableDocuments)
        if (!imageDocument) return
        const image = await getHorseDocumentFile(imageDocument.documentId)
        objectUrl = URL.createObjectURL(image)
        if (active) setImageUrl(objectUrl)
        else {
          URL.revokeObjectURL(objectUrl)
          objectUrl = ''
        }
      } catch {
        if (active) setImageUnavailable(true)
      } finally {
        if (active) setImageLoading(false)
      }
    }

    void loadImage()
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [documents, horseId])

  return (
    <div
      className={`horse-avatar horse-avatar-${size}${imageUrl ? ' has-image' : ''}`}
      role="img"
      aria-label={imageUrl ? `Ảnh ${name || 'ngựa'}` : `${name || 'Ngựa'}: ${imageLoading ? 'Đang tải ảnh' : imageUnavailable ? 'Ảnh không tải được' : 'Chưa có ảnh'}`}
      title={imageUnavailable ? 'Ảnh không tải được' : undefined}
    >
      {imageUrl ? (
        <img src={imageUrl} alt="" onError={() => { setImageUrl(''); setImageUnavailable(true) }} />
      ) : (
        <>
          <svg viewBox="0 0 48 48" aria-hidden="true" fill="none">
            <path d="M13 36c1-7 4-12 10-14l-4-7 7 3 6-6 1 9c4 3 6 8 5 15H13Z" />
            <path d="m23 20 3 4m7-3h.1M14 35h25" />
          </svg>
          <span>{imageLoading ? 'Đang tải ảnh...' : 'Chưa có ảnh'}</span>
        </>
      )}
    </div>
  )
}

export default HorseAvatar
