import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
// In development the browser talks to Vite on :5173 and Vite forwards /api/* to Django,
// so the backend needs no CORS change. Override the target with VITE_PROXY_TARGET.
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, '.', '');
    return {
        plugins: [react()],
        server: {
            // Only this computer can open the site while developing. Anyone on the same Wi-Fi could otherwise reach the
            // login pages (the admin one too). To test from a phone, start with VITE_HOST=true.
            host: env.VITE_HOST === 'true' ? true : 'localhost',
            port: 5173,
            proxy: {
                // Uploaded pictures are served from /media/ by the same Django server.
                '/api': {
                    target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
                '/media': {
                    target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
                    changeOrigin: true,
                },
            },
        },
    };
});
