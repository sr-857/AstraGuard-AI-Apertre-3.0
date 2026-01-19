import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(() => {
  const config = {
    plugins: [react()],
  }

  // Development-only settings
  // config.server = {
  //   port: 5173,
  //   strictPort: false,
  //   host: '0.0.0.0',
  //   allowedHosts: [
  //     'localhost',
  //     '127.0.0.1',
  //     '.loca.lt',
  //   ],
  // }

  return config
})