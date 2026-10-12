import { accessTokenKey } from '../config/api.js'
import { apiPost } from './apiClient.js'

export async function login(email, password) {
  const session = await apiPost('/auth/login', { Email: email, Password: password })
  localStorage.setItem(accessTokenKey, session.access)
  return session.User
}

export function logout() {
  localStorage.removeItem(accessTokenKey)
}

