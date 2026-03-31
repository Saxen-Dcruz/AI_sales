import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Binds to 0.0.0.0 so Docker can map it
    port: 5173, // Vite's default port
    watch: {
      usePolling: true, // CRITICAL: Forces Vite to notice file changes inside Docker
    }
  },
})