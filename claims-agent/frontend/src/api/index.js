const BASE = '/api/v1'

async function request(url, opts = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  // Auth
  login: async (data) => { const r = await fetch(BASE+'/auth/login/', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) }); return r.json() },
  logout: () => request('/auth/logout/', { method: 'POST' }),
  me: () => request('/auth/me/'),

  // Cases
  listCases: (params = {}) => request('/cases/?' + new URLSearchParams(params)),
  getCase: (id) => request(`/cases/${id}/`),
  createCase: (data) => request('/cases/', { method: 'POST', body: JSON.stringify(data) }),
  auditCase: (id) => request(`/cases/${id}/audit/`, { method: 'POST' }),
  batchAudit: (ids) => request('/cases/batch_audit/', { method: 'POST', body: JSON.stringify({ case_ids: ids }) }),
  cancelCase: (id) => request(`/cases/${id}/cancel/`, { method: 'POST' }),
  supplement: (id) => request(`/cases/${id}/supplement/`, { method: 'POST' }),
  intervene: (id, data) => request(`/cases/${id}/intervene/`, { method: 'POST', body: JSON.stringify(data) }),

  // Rules
  listRules: () => request('/rules/'),
  // Sync
  syncCases: (data) => request('/cases/sync/', { method: 'POST', body: JSON.stringify(data) }),
}

// WebSocket
export function connectWS(caseId, onMessage) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/cases/${caseId}/`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  ws.onclose = () => setTimeout(() => connectWS(caseId, onMessage), 2000)
  return ws
}
