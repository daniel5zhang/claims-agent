import request from './request'

export function generateManual(schemeId) {
  return request.post('/manual/generate', { scheme_id: schemeId })
}

export function getManual(manualId) {
  return request.get(`/manual/${manualId}`)
}

export function downloadManual(manualId) {
  window.open(`/api/manual/${manualId}/download`, '_blank')
}
