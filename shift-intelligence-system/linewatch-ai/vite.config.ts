import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: "/Google-Deepmind-Hackathon/",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split react-icons into separate chunk (lazy loaded)
          'react-icons': ['react-icons/fa', 'react-icons/md'],
          // Split large visualization libs
          'viz-libs': ['reactflow', 'konva', 'react-konva'],
          // Split charts (only for analytics page)
          'charts': ['recharts'],
        }
      }
    }
  }
})
