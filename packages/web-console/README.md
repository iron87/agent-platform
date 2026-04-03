# Web Console (Phase 1-3)

Operator UI for profile management and health checks.

## Current status
Implemented through tasks T001-T020:
- profile CRUD + persistence
- proxy/direct API mode selection
- health check execution
- operation history panel

Other modules (agents, run, session, jobs, approvals) are placeholders in current build.

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

## How to use (MVP)
1. Create a profile in left panel:
   - name
   - base URL (for local backend typically `http://localhost:8000`)
   - mode: `direct` for local/dev or `proxy` for backend-routed mode
   - API key (masked by default, reveal with explicit action)
2. Select the profile as active.
3. Go to Health module and click Run health check.
4. Inspect response/error in Operation history on the right.

## Notes on auth/security model
- v1 follows network-scoped operator access (no per-user sign-in UI yet).
- In direct mode, browser sends `Authorization: Bearer <apiKey>` to selected base URL.
- In proxy mode, frontend targets `/api/*` and expects backend-side credential handling.

## Troubleshooting
- Empty/failed health response:
  - verify backend is reachable at profile base URL
  - verify API key is valid for your tenant
- Build errors after dependency changes:
  - rerun `npm install` from repository root
- Port conflict on 5174:
  - stop other Vite processes or change port in `packages/web-console/vite.config.ts`
