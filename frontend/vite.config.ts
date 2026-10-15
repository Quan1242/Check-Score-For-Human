import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const { M49_BACKEND_PORT = '8000' } = loadEnv(mode, '.', 'M49_');
  return {
    plugins: [react()],
    server: {
      proxy: { '/api': `http://127.0.0.1:${M49_BACKEND_PORT}` },
    },
  };
});
