import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: new Array(react()),
  base: '/mlb-prop-engine/',
})