import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// in dev, send /api and /assistant to the local services
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', rewrite: p => p.replace(/^\/api/, '') },
      '/assistant': { target: 'http://localhost:5000', rewrite: p => p.replace(/^\/assistant/, '') },
    },
  },
})
