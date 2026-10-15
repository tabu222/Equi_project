import type { User } from '../types';
import { ApiError, apiGet, apiPost, apiPostPublic, saveSession } from './apiClient';

type ApiRecord = Record<string, unknown>;

export interface LoginResult {
  access: string;
  refresh: string;
  user: User;
}

export function normalizeUser(value: unknown): User {
  if (!value || typeof value !== 'object') throw new ApiError('API trả tài khoản không đúng định dạng.');
  const record = value as ApiRecord;
  const rawId = record.UserID;
  if (typeof rawId !== 'number' && typeof rawId !== 'string') {
    throw new ApiError('API trả thiếu mã UserID.');
  }
  const roles = Array.isArray(record.Roles) ? record.Roles : [];
  const roleMap: Record<string, User['role']> = {
    CLUB_MANAGER: 'CLUB_MANAGER',
    HORSE_OWNER: 'OWNER',
    VETERINARIAN: 'VET',
  };
  const role = roles.map((item) => roleMap[String(item)]).find(Boolean);
  if (!role) throw new ApiError(`Tài khoản UserID ${rawId} không có vai trò Flow 1 được hỗ trợ.`);
  return {
    id: String(rawId),
    clubId: record.ClubID == null ? '' : String(record.ClubID),
    fullName: typeof record.FullName === 'string' ? record.FullName : '',
    email: typeof record.Email === 'string' ? record.Email : '',
    phone: typeof record.Phone === 'string' ? record.Phone : '',
    address: typeof record.Address === 'string' ? record.Address : '',
    createdAt: typeof record.CreatedAt === 'string' ? record.CreatedAt : '',
    role,
    permissions: Array.isArray(record.Permissions)
      ? record.Permissions.filter((item): item is string => typeof item === 'string')
      : [],
    isActive: record.Status === 'Active',
  };
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const result = await apiPostPublic<ApiRecord>('/auth/login', { Email: email, Password: password });
  if (typeof result.access !== 'string' || typeof result.refresh !== 'string' || !result.User) {
    throw new ApiError('API đăng nhập trả thiếu token hoặc thông tin tài khoản.');
  }
  const user = normalizeUser(result.User);
  saveSession(result.access, result.refresh);
  return { access: result.access, refresh: result.refresh, user };
}

export async function getCurrentUser(): Promise<User> {
  return normalizeUser(await apiGet<unknown>('/auth/me'));
}

export async function getUsers(roleCode?: string): Promise<User[]> {
  const suffix = roleCode ? `?RoleCode=${encodeURIComponent(roleCode)}` : '';
  const result = await apiGet<unknown>(`/users${suffix}`);
  if (!Array.isArray(result)) throw new ApiError('API trả danh sách người dùng không đúng định dạng.');
  return result.map(normalizeUser);
}

export async function createUser(payload: {
  fullName: string;
  email: string;
  phone: string;
  address: string;
  roleCode?: string;
  password?: string;
}): Promise<User & { temporaryPassword?: string }> {
  const result = await apiPost<unknown>('/users', {
    FullName: payload.fullName,
    Email: payload.email,
    Phone: payload.phone,
    Address: payload.address,
    RoleCode: payload.roleCode ?? 'HORSE_OWNER',
    ...(payload.password ? { Password: payload.password } : {}),
  });
  const user = normalizeUser(result);
  return {
    ...user,
    temporaryPassword: result && typeof result === 'object'
      && typeof (result as ApiRecord).TemporaryPassword === 'string'
      ? (result as ApiRecord).TemporaryPassword as string
      : undefined,
  };
}
