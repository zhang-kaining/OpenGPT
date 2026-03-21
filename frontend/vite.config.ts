import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const openGptApiPort = process.env.OpenGPT_API_PORT || '18789'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${openGptApiPort}`,
        changeOrigin: true,
      },
    },
  },
})
