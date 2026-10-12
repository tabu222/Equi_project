import { accessTokenKey, apiBaseUrl, refreshTokenKey } from '../config/api.js'

export class ApiError extends Error {
  constructor(message, status, code = '', fields = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

let refreshPromise

async function refreshAccessToken() {
  const refresh = localStorage.getItem(refreshTokenKey)
  if (!refresh) {
    localStorage.removeItem(accessTokenKey)
    window.dispatchEvent(new Event('equi:unauthorized'))
    return null
  }
  if (!refreshPromise) {
    refreshPromise = fetch(`${apiBaseUrl}/auth/refresh`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    }).then(async (response) => {
      if (!response.ok) return null
      const session = await response.json()
      if (session.access) localStorage.setItem(accessTokenKey, session.access)
      return session.access || null
    }).catch(() => null).finally(() => { refreshPromise = null })
  }
  const access = await refreshPromise
  if (!access) {
    localStorage.removeItem(accessTokenKey)
    localStorage.removeItem(refreshTokenKey)
    window.dispatchEvent(new Event('equi:unauthorized'))
  }
  return access
}

async function request(path, options = {}, retried = false) {
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
  } catch {
    throw new ApiError('Không thể kết nối máy chủ. Kiểm tra kết nối mạng rồi thử lại.')
  }

  if (response.status === 401 && !retried && path !== '/auth/login' && path !== '/health') {
    const access = await refreshAccessToken()
    if (access) return request(path, options, true)
  }

  if (!response.ok) {
    let message = `Yêu cầu thất bại (${response.status}).`
    let code = ''
    let fields = null
    try {
      const body = await response.json()
      code = body.code || ''
      fields = body
      message = body.detail || Object.entries(body).filter(([key]) => key !== 'code').map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' ') || message
    } catch {
      // Keep the status message when the server response is not JSON.
    }
    throw new ApiError(message, response.status, code, fields)
  }
  if (response.status === 204) return undefined
  return response.json()
}

export const apiGet = (path) => request(path)
export const apiPost = (path, payload) => request(path, { method: 'POST', body: JSON.stringify(payload ?? {}) })
export const apiPatch = (path, payload) => request(path, { method: 'PATCH', body: JSON.stringify(payload ?? {}) })
export const apiDelete = (path) => request(path, { method: 'DELETE' })

