import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // Binds to 0.0.0.0 so Docker can map it
    port: 5173,
    watch: {
      usePolling: true,  // Required for file change detection inside Docker
    },
    hmr: {
      clientPort: 5173,  // Tells the browser WebSocket to connect on the mapped port
    },
  },
})