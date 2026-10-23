import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// base './' so the build works from any GitHub Pages sub-path
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
})
