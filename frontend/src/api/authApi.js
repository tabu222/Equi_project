import { accessTokenKey, refreshTokenKey } from '../config/api.js'
import { apiPost } from './apiClient.js'

export async function login(email, password) {
  const session = await apiPost('/auth/login', { Email: email, Password: password })
  localStorage.setItem(accessTokenKey, session.access)
  if (session.refresh) localStorage.setItem(refreshTokenKey, session.refresh)
  return session.User
}

export function logout() {
  localStorage.removeItem(accessTokenKey)
  localStorage.removeItem(refreshTokenKey)
}

