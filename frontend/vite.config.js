import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // Keeps it accessible on your local network
    allowedHosts: ['cms.footprints.work'] // Allows your public domain
  }
})
