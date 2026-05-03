import axios from 'axios'

const STORAGE_KEY = 'admin_token'

// Always use a relative path so both Vite proxy (/api → localhost:8001)
// and Nginx proxy (/api/ → Railway backend) work without CORS.
// If VITE_API_URL is explicitly set to an external origin, honour it.
const BASE_URL = (() => {
  const raw = import.meta.env.VITE_API_URL as string | undefined
  if (raw && raw.startsWith('http')) {
    return raw.replace(/\/api\/v1\/?$/, '/api/v1/admin')
  }
  return '/api/v1/admin'
})()

export const adminApi = axios.create({ baseURL: BASE_URL })

adminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEY)
  if (token) config.headers['X-Admin-Token'] = token
  return config
})

adminApi.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 403) {
      localStorage.removeItem(STORAGE_KEY)
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

export const getToken = () => localStorage.getItem(STORAGE_KEY)
export const setToken = (t: string) => localStorage.setItem(STORAGE_KEY, t)
export const clearToken = () => localStorage.removeItem(STORAGE_KEY)
