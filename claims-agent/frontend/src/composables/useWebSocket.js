
import { ref, onUnmounted } from 'vue'
export function useWebSocket(caseId) {
  const events = ref([]); let ws = null; let retries = 0
  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/ws/cases/${caseId}/`)
    ws.onmessage = (e) => events.value.push(JSON.parse(e.data))
    ws.onclose = () => { if (retries < 5) { retries++; setTimeout(connect, [1000,2000,4000,8000,16000][retries-1]) } }
    ws.onopen = () => { retries = 0 }
  }
  connect()
  onUnmounted(() => ws && ws.close())
  return { events }
}
