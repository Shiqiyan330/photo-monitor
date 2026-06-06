import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/admin': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/office-data': 'http://127.0.0.1:8000',
      '/photos': 'http://127.0.0.1:8000',
      '/structure': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
