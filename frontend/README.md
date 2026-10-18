# CollabNest: frontend

React single-page app for the CollabNest marketplace (brands and micro-influencers). It talks to the
Django REST API in the repository root and has no data of its own.

## Run it

You need Node 20 or newer and the backend running on port 8000 (see the root README).

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In development the app calls `/api/v1/...` on its own origin and the Vite
dev server forwards `/api` to `http://127.0.0.1:8000`, so the backend needs no CORS change.

| Variable | When | Purpose |
|---|---|---|
| `VITE_API_URL` | production build | Public API origin including the version prefix, e.g. `https://api.example.com/api/v1`. When set, the browser calls it directly, so list the frontend origin in the backend's `CORS_ALLOWED_ORIGINS`. |
| `VITE_PROXY_TARGET` | development | Where the dev server forwards `/api`. Defaults to `http://127.0.0.1:8000`. |

Put overrides in `.env.local` (see `.env.example`).

```bash
npm run build     # type-check, then build into dist/
npm run preview   # serve the production build locally
```

`vercel.json` rewrites every path to `index.html` so deep links survive a refresh.

## Design

The look comes from the CollabNest logo (`public/collabnest-logo.svg`).

- **Colour:** navy ink (`ink`, with 700 = the logo navy), cool surfaces (`mist`), the logo's blue (`brand`) and
  the teal at the start of its arc (`nest`). Tokens live in `tailwind.config.js`; shared component classes
  (`.btn`, `.card`, `.tag`, `.input`, ...) live in `src/index.css`.
- **Type:** Bricolage Grotesque for headings, Figtree for text, JetBrains Mono for small data labels.
- **Signature:** the logo's arc. It draws itself in the landing hero between a brief and a creator, and
  returns on the navy panels (`src/components/ArcMark.tsx`). Nothing else on the page is decorative.
- **Logo:** `src/components/Logo.tsx` draws the wordmark and the loop mark inline, with a `default`
  (navy) and an `invert` (white) variant.

`docs/FRONTEND_SYSTEM_DESIGN.md` is the original architecture write-up. Its endpoint table is a proposal;
the real contract is [`../docs/openapi.yml`](../docs/openapi.yml) and `src/api/endpoints.ts`.

## Structure

```
src/
  api/          client.ts (fetch wrapper, errors, token) and endpoints.ts (typed calls and mappers)
  components/   AppShell, PublicLayout, AuthShell, Logo, ArcMark, ui kit
  pages/        public, auth, creator, brand, shared, admin
  state/        AuthContext, AdminAuthContext, Store (API-backed cache), ToastContext
```

Screens never see raw API field names: `endpoints.ts` maps snake_case responses to the UI types in
`src/types.ts`.
