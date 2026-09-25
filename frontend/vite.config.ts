import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5211,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8911', changeOrigin: true } },
  },
  preview: { port: 5211, proxy: { '/api': { target: 'http://127.0.0.1:8911', changeOrigin: true } } },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
    // No manualChunks: forcing recharts into a named chunk dragged shared deps into it and made the
    // entry preload it on every page. Rollup's own splitting keeps maplibre (WorldMap, lazy) and
    // recharts (chart pages) out of the entry.
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/[name]-[hash].js',
      },
    },
  },
})
