import request from './request'

export function sendMessage(sessionId, message) {
  return request.post('/chat/send', {
    session_id: sessionId,
    message
  })
}

export function sendMessageAsync(sessionId, message) {
  return request.post('/chat/send-async', {
    session_id: sessionId,
    message
  })
}

export function getTaskStatus(taskId) {
  return request.get(`/chat/task/${taskId}`)
}

export function getHistory(sessionId) {
  return request.get(`/chat/history/${sessionId}`)
}

export function getSessions() {
  return request.get('/chat/sessions')
}

export function deleteSession(sessionId) {
  return request.delete(`/chat/sessions/${sessionId}`)
}
