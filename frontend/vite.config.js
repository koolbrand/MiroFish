import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const buildDate = new Date().toISOString().slice(0, 10) // YYYY-MM-DD

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // Las VITE_* viven en el .env de la raíz del repo
  envDir: path.resolve(__dirname, '..'),
  define: {
    __APP_VERSION__: JSON.stringify('v0.2'),
    __BUILD_DATE__: JSON.stringify(buildDate)
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@locales': path.resolve(__dirname, '../locales')
    }
  },
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
