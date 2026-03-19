import { ref, computed } from 'vue'

export interface AuthUser {
  id: string
  username: string
  display_name: string
}

const TOKEN_KEY = 'auth-token'
const USER_KEY = 'auth-user'

const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
const user = ref<AuthUser | null>(
  (() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') }
    catch { return null }
  })()
)

export const isLoggedIn = computed(() => !!token.value && !!user.value)
export const currentUser = computed(() => user.value)
export const authToken = computed(() => token.value)

export function setAuth(t: string, u: AuthUser) {
  token.value = t
  user.value = u
  localStorage.setItem(TOKEN_KEY, t)
  localStorage.setItem(USER_KEY, JSON.stringify(u))
}

export function clearAuth() {
  token.value = null
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getAuthHeaders(): Record<string, string> {
  if (!token.value) return {}
  return { Authorization: `Bearer ${token.value}` }
}
