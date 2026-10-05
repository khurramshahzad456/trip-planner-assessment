import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // In development, /api is proxied to Django so no CORS setup is needed.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('leaflet')) return 'map'
          if (id.includes('jspdf') || id.includes('html2canvas') || id.includes('canvg')) return 'pdf'
          return undefined
        },
      },
    },
  },
  test: { environment: 'node' },
})
