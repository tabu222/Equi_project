// Luật kiểm tra form lý lịch ngựa, dùng chung cho form của Owner và Manager (khớp với HorseWriteSerializer ở backend).

export const apiFieldNames = {
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
  OwnerID: 'ownerId',
}

export function dateValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function validateHorseForm(form, { requireClub = false, requireOwner = false } = {}) {
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
  if (requireOwner && !form.ownerId) return 'Vui lòng chọn chủ ngựa.'
  const missing = requiredFields.find(([key]) => !String(form[key] ?? '').trim())
  if (missing) return `Vui lòng nhập ${missing[1].toLowerCase()}.`
  if (requireClub && !form.clubId) return 'Vui lòng chọn câu lạc bộ muốn đăng ký.'
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

export function cleanHorsePayload(form) {
  return {
    ...form,
    name: form.name.trim(),
    breed: form.breed.trim(),
    coatColor: form.coatColor.trim(),
    registrationNumber: form.registrationNumber.trim().toUpperCase(),
    microchipNumber: form.microchipNumber.trim(),
    sireName: form.sireName.trim(),
    damName: form.damName.trim(),
  }
}

// Gom lỗi theo trường từ ApiError (400) về đúng ô trên form
export function mapFieldErrors(apiFieldErrors) {
  const fieldErrors = {}
  let unmapped = false
  Object.entries(apiFieldErrors).forEach(([apiField, messages]) => {
    const field = apiFieldNames[apiField]
    if (field) fieldErrors[field] = messages.join(' ')
    else unmapped = true
  })
  return { fieldErrors, unmapped }
}
