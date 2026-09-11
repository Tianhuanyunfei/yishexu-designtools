import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import fs from 'fs'

// 读取package.json文件获取版本号
const packageJson = JSON.parse(fs.readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))
const version = packageJson.version

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  define: {
    // 定义全局变量，方便前端代码获取版本号
    '__APP_VERSION__': JSON.stringify(version),
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 方管排布 deep 搜索可能数分钟，避免开发代理先断开
        timeout: 5 * 60 * 1000,
        proxyTimeout: 5 * 60 * 1000,
      },
    },
  },
})