export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || '/api'
).replace(/\/$/, '')

export const accessTokenKey = 'equi_access_token'

export const refreshTokenKey = 'equi_refresh_token'

export const apiEndpoints = {
  health: `${apiBaseUrl}/health`,
}