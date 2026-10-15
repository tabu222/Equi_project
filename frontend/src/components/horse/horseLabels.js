const genderLabels = { Male: 'Đực', Female: 'Cái', Gelding: 'Đực đã thiến', MALE: 'Đực', FEMALE: 'Cái', GELDING: 'Đực đã thiến', UNKNOWN: 'Chưa có thông tin' }

export function formatHorseGender(gender) {
  return genderLabels[gender] || gender || 'Chưa có thông tin'
}
