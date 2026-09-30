import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: same-origin /api -> FastAPI backend at 127.0.0.1:8000.
// The built app is served by the backend, so all fetches stay same-origin /api.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
