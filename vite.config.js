import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // All /imgs/... requests are forwarded to Flask on port 5000
      // which serves them from the actual image-extraction folder.
      '/imgs': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: false,
      },
    },
  },
})
