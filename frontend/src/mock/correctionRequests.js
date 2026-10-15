// Frontend request-history fixtures kept separate from verified Horse records.
export const correctionRequestRecords = [
  {
    requestId: 'CR-101',
    horseId: 1,
    ownerId: 101,
    field: 'dateOfBirth',
    requestedValue: '2021-04-10',
    reason: 'Ngày sinh trên giấy tờ cần được đối chiếu.',
    evidenceFiles: ['Giấy đăng ký ngựa.pdf'],
    status: 'Rejected',
    rejectionReason: 'Tài liệu đính kèm chưa thể hiện rõ ngày sinh.',
    createdAt: '2026-09-28T10:15:00',
  },
]
