import { apiGetPublic } from './apiClient.ts'

export function getHealth(signal) {
  return apiGetPublic('/health', { signal })
}
