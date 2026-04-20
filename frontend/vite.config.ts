import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()], //activate react plugin
  server: {
    port: 3000, //default is 5173
    proxy: {
      '/api': { //any request that starts with /api is intercepted by vite instead of going to browser's network
        target: 'http://localhost:8000',  //eventual express server (maybe later http://backend:8000)
        changeOrigin: true, //prevents server-side CORS rejections
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
