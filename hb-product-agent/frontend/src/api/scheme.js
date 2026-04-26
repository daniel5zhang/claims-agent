import request from './request'

export function getScheme(schemeId) {
  return request.get(`/scheme/${schemeId}`)
}

export function confirmScheme(schemeId, confirmed = true) {
  return request.post(`/scheme/${schemeId}/confirm`, { scheme_id: schemeId, confirmed })
}

export function adjustScheme(schemeId, adjustmentPrompt) {
  return request.post(`/scheme/${schemeId}/adjust`, {
    scheme_id: schemeId,
    adjustment_prompt: adjustmentPrompt
  })
}

export function getSchemeByConversation(conversationId) {
  return request.get(`/scheme/conversation/${conversationId}`)
}

export function updateScheme(schemeId, data) {
  return request.post(`/scheme/${schemeId}/update`, data)
}
