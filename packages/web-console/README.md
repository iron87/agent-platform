# Web Console

Operator UI for API/CLI parity workflows:
- profile CRUD + persistence
- health checks
- agents list/create
- run + replay
- session chat with local conversation persistence
- async jobs polling + approval handling
- operation history with consistent feedback states and toasts

## Prerequisites
- Node.js 20+
- Root workspace dependencies installed (`npm install` at repository root)
- Backend running (for direct mode, default base URL is `http://localhost:8000`)

## Run in development
From repository root:

```bash
npm run web:dev
```

Open:
- http://localhost:5174

Dev proxy behavior:
- In `proxy` mode, frontend calls `/api/*` and Vite forwards to `http://localhost:8000/api/v1/*`.
- In `direct` mode, frontend calls your profile base URL and appends `/api/v1` automatically.

## Build
From repository root:

```bash
npm run web:build
```

## Typecheck
From repository root:

```bash
npm run web:typecheck
```

## Test
From repository root:

```bash
npm run web:test
```

## How to use
1. Create a profile in left panel:
   - name
  - base URL (for local backend typically `http://localhost:8000`; app appends `/api/v1` automatically in direct mode)
   - mode: `direct` for local/dev or `proxy` for backend-routed mode
   - API key (masked by default, reveal with explicit action)
2. Select the profile as active.
3. Use module navigation to operate agents, run/replay, session chat, jobs, and approvals.
4. Inspect response/error in Operation history on the right.

## Notes on auth/security model
- v1 follows network-scoped operator access (no per-user sign-in UI yet).
- In direct mode, browser sends both `X-API-Key` and `Authorization` headers to the API.
- In proxy mode, frontend targets `/api/*` and expects backend-side credential handling.

## Known limitations (v1)
- no dedicated web-console audit trail storage
- no per-user auth in UI
- job updates rely on polling (2s interval, 5m default timeout), not real-time push

## Troubleshooting
- Empty/failed health response:
  - verify backend is reachable at profile base URL
  - verify API key is valid for your tenant
- Build errors after dependency changes:
  - rerun `npm install` from repository root
- Port conflict on 5174:
  - stop other Vite processes or change port in `packages/web-console/vite.config.ts`
