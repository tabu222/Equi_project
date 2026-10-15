import { apiEndpoints } from '../config/api.js'

export async function getHealth(signal) {
  const response = await fetch(apiEndpoints.health, {
    headers: { Accept: 'application/json' },
    signal,
  })

  const health = await response.json()

  if (!health.backend || !health.database) {
    throw new Error('Unexpected health response')
  }

  return health
}
