import axios from 'axios'
import { getUserId, setUserId } from '../utils/user'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：注入 X-User-ID
request.interceptors.request.use((config) => {
  config.headers['X-User-ID'] = getUserId()
  return config
})

request.interceptors.response.use(
  (response) => {
    // 保存服务端回传的 user_id
    const serverUserId = response.headers['x-user-id']
    if (serverUserId) {
      setUserId(serverUserId)
    }
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default request
