import react from '@vitejs/plugin-react'
import { cpSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const replay = process.env.VITE_REPLAY === '1'
const webRoot = path.dirname(fileURLToPath(import.meta.url))

function copyReplayData() {
  return {
    name: 'copy-replay-data',
    buildStart() {
      const src = path.resolve(webRoot, '../../replay')
      const dest = path.resolve(webRoot, 'public/replay')
      if (!existsSync(src)) return
      cpSync(src, dest, { recursive: true })
    },
  }
}

export default defineConfig({
  base: replay ? './' : '/',
  plugins: [
    react(),
    copyReplayData(),
    {
      name: 'replay-html',
      transformIndexHtml(html) {
        if (!replay) return html
        return html
          .replace(/\s*<link rel="preconnect"[^>]*>/g, '')
          .replace(/\s*<link\s+href="https:\/\/fonts\.googleapis\.com[^>]*>/g, '')
          .replace('<title>Proof-of-Change console</title>', '<title>Proof-of-Change results</title>')
      },
    },
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8787',
    },
  },
})
