const genderLabels = { Male: 'Đực', Female: 'Cái' }

export function formatHorseGender(gender) {
  return genderLabels[gender] || gender || 'Chưa có thông tin'
}
