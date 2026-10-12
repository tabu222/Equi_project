import { apiGet } from './apiClient.js'
import { normalizeUser } from './horseApi.js'

export async function getUsers(roleCode) {
  const users = await apiGet(`/users${roleCode ? `?RoleCode=${encodeURIComponent(roleCode)}` : ''}`)
  return users.map(normalizeUser)
}

