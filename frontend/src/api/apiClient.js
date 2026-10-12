import { accessTokenKey, apiBaseUrl } from '../config/api.js'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  const token = localStorage.getItem(accessTokenKey)
  let response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Không thể kết nối máy chủ.')
  }

  if (!response.ok) {
    let message = `Yêu cầu thất bại (${response.status}).`
    try {
      const body = await response.json()
      message = body.detail || Object.values(body).flat().join(' ') || message
    } catch {
      // Keep the status message when the server response is not JSON.
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined
  return response.json()
}

export const apiGet = (path) => request(path)
export const apiPost = (path, payload) => request(path, { method: 'POST', body: JSON.stringify(payload ?? {}) })
export const apiPatch = (path, payload) => request(path, { method: 'PATCH', body: JSON.stringify(payload ?? {}) })

