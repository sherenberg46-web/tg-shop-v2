import axios from "axios"
import { useStore } from "@/store"

// VITE_API_URL is injected at build time by Dockerfile ARG.
// Set it in Railway frontend service env vars:
//   VITE_API_URL = https://tg-shop-production-1b03.up.railway.app/api/v1
// Falls back to nginx proxy for local dev.
const BASE_URL =
  import.meta.env.VITE_API_URL || "https://tg-shop-production-1b03.up.railway.app/api/v1"

const api = axios.create({
  baseURL: BASE_URL,
})

// Attach Telegram user_id to every request
api.interceptors.request.use((config) => {
  const userId = useStore.getState().userId
  if (userId) config.headers["X-User-Id"] = String(userId)
  return config
})

export default api
