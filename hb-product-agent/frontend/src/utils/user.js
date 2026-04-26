/**
 * 用户ID管理
 * 首次访问自动生成 UUID，存入 localStorage
 */
const USER_ID_KEY = 'hb_agent_user_id'

export function getUserId() {
  let id = localStorage.getItem(USER_ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(USER_ID_KEY, id)
  }
  return id
}

export function setUserId(id) {
  if (id) {
    localStorage.setItem(USER_ID_KEY, id)
  }
}
