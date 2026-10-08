# Animeshka Upscale — frontend

React 19 + TypeScript + Vite + Tailwind. See the [project README](../README.md) for the whole stack.

All commands run from this directory (`frontend/`):

```bash
npm ci
npm run dev       # http://localhost:5173, /api and /health are proxied to the API on :8000
npm run build     # type-check + production build into dist/
npm run lint      # oxlint
```

In Docker the built app is served by nginx (`nginx.conf`), which proxies `/api` to the `api`
service, so the app should always call relative URLs (`/api/...`).
