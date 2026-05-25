import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  base: './',
  build: {
    outDir: 'dist',
    input: {
      main: 'index.html',
      login: 'login.html',
      ocr: 'pages/ocr.html',
      exam: 'pages/exam.html',
      diagnosis: 'pages/diagnosis.html',
      students: 'pages/students.html',
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
