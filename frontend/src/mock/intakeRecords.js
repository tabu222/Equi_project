// Frontend intake view-model fixtures; these fields are not Horse database columns.
export const intakeRecords = [
  {
    horseId: 3,
    vetConclusionStatus: 'Eligible',
    vetConclusion: 'Đủ điều kiện tiếp nhận.',
    blockingReason: '',
  },
  {
    horseId: 5,
    vetConclusionStatus: 'Blocked',
    vetConclusion: 'Chưa đủ điều kiện tiếp nhận.',
    blockingReason: 'Cần có kết luận thú y trước khi hoàn tất tiếp nhận.',
  },
]
