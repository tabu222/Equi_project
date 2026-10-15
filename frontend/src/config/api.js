const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export const apiEndpoints = {
  health: `${apiBaseUrl}/health`,
}
