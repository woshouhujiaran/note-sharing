import { getAiBffOrigin } from '@/config/ai'

function getAiToken() {
  return localStorage.getItem('token') || ''
}

function buildAiHeaders() {
  const headers = {
    'Content-Type': 'application/json'
  }

  const token = getAiToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return headers
}

export async function postAiJson(path, payload) {
  const origin = getAiBffOrigin().replace(/\/$/, '')
  const response = await fetch(`${origin}${path}`, {
    method: 'POST',
    headers: buildAiHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(body || `AI BFF ${response.status}`)
  }

  return response.json()
}

export async function probeAiBff() {
  const origin = getAiBffOrigin().replace(/\/$/, '')
  const response = await fetch(`${origin}/health`, {
    method: 'GET',
    headers: buildAiHeaders()
  })

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(body || `AI BFF ${response.status}`)
  }

  return response.json()
}

export function buildAiRequestContext(resource, extras = {}) {
  return {
    version: '1.0',
    page: extras.page || {},
    resource,
    user: extras.user || {},
    permissions: extras.permissions || {}
  }
}
