import path from 'path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import proxyOptions from './proxyOptions';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: '../frappe_pilot/public/pilot',
    emptyOutDir: true,
  },
  server: {
    port: 8081,
    proxy: proxyOptions,
  },
});
