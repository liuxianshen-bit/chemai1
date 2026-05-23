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
      questions: 'pages/questions.html',
      diagnosis: 'pages/diagnosis.html',
      report: 'pages/report.html',
      panel: 'pages/panel.html',
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
