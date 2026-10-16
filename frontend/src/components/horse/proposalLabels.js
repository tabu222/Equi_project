export const proposalFields = [
  ['HorseName', 'Tên ngựa', 'name', 100], ['Breed', 'Giống', 'breed', 100],
  ['DateOfBirth', 'Ngày sinh', 'dateOfBirth'], ['Gender', 'Giới tính', 'sex'],
  ['CoatColor', 'Màu lông', 'coatColor', 50], ['SireName', 'Tên ngựa cha', 'sireName', 100],
  ['DamName', 'Tên ngựa mẹ', 'damName', 100], ['MicrochipNumber', 'Số microchip', 'microchipNumber', 30],
  ['PassportNumber', 'Số hộ chiếu / đăng ký', 'registrationNumber', 50],
]
export const purposeLabels = { avatar: 'Đề nghị làm ảnh đại diện', image: 'Ảnh mới', evidence: 'Minh chứng', add: 'Bổ sung tài liệu', replace: 'Phiên bản đề nghị' }
export const documentTypeLabels = { Passport: 'Hộ chiếu', 'Microchip Certificate': 'Chứng nhận microchip', 'Ownership Proof': 'Chứng minh sở hữu', 'Handover Record': 'Biên bản bàn giao', Contract: 'Hợp đồng', Other: 'Khác' }
export const proposalStatusLabels = { Pending: 'Chờ duyệt', Approved: 'Đã duyệt', Rejected: 'Đã từ chối', Withdrawn: 'Đã rút' }
export function displayProposalValue(value) {
  return ({ Male: 'Đực', Female: 'Cái', Gelding: 'Đực đã thiến', MALE: 'Đực', FEMALE: 'Cái', GELDING: 'Đực đã thiến' })[value] || value || 'Chưa có thông tin'
}

