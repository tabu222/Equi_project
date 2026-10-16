import { apiPostPublic } from './apiClient.ts'

// Confirmed in backend/apps/accounts/urls.py and OwnerRegisterSerializer.
// Registration always creates HORSE_OWNER; no client-controlled RoleCode.
export async function registerOwner({ fullName, email, phone, address, clubId, password }) {
  const result = await apiPostPublic('/auth/register', {
    FullName: fullName, Email: email, Phone: phone, Address: address,
    ClubID: Number(clubId), Password: password,
  })
  if (!result?.User?.UserID || !result.access || !result.refresh) {
    throw new Error('API đăng ký trả thiếu thông tin. Hãy thử đăng nhập để kiểm tra tài khoản trước khi đăng ký lại.')
  }
  return result.User
}
