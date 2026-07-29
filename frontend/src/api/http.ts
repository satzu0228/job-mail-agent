import axios, { AxiosError } from 'axios'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 90_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export function getApiErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    if (!error.response) return '无法连接后端服务，请确认 FastAPI 已启动'
  }
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}
