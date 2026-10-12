import { apiGet } from './apiClient.js'
import { normalizeUser } from './horseApi.js'

export async function getUsers() {
  const users = await apiGet('/users')
  return users.map(normalizeUser)
}

