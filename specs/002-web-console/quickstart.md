# Quickstart: Web Console Feature

## Prerequisites
- Node.js 20+
- Existing backend/API stack available locally (see project README and infra compose)
- Access to an API key for local direct mode testing

## 1. Start backend dependencies
Use existing repository workflow to bring up API services and dependencies.

## 2. Create frontend package skeleton
From repository root, initialize `packages/web-console` with Vite React TypeScript template.

## 3. Install UI dependencies
Install and configure:
- `tailwindcss`, `postcss`, `autoprefixer`
- `class-variance-authority`, `clsx`, `tailwind-merge`
- `lucide-react`
- `shadcn/ui` initialization with Tailwind config

## 4. Configure base app shell
- Add layout with left profile panel and right operation panels.
- Wire route/state structure for modules:
- Health
- Agents
- Run/Replay
- Session Chat
- Jobs
- Approvals

## 5. Implement API client modes
- `proxy` mode for production calls through backend endpoint(s)
- `direct` mode for local/dev using profile API key header
- Centralize request building and error normalization

## 6. Implement profile persistence and masking
- Store profiles in local storage
- Mask API keys by default in UI
- Add explicit reveal interaction and clear warnings

## 7. Implement operation modules
- Health: GET health endpoint and render status
- Agents: list/create
- Run: execute and display structured result
- Replay: rerun from prior run
- Session Chat: send message, append transcript
- Jobs: submit + status polling every 2s, timeout at 5 minutes
- Approvals: list pending and approve/reject actions

## 8. Testing
- Unit tests for profile store and API client behavior
- Component tests for each panel happy path + error state
- One integration-style test for polling timeout behavior

## 9. Documentation
Update README with:
- console package setup/run instructions
- security model (hybrid mode + network trust assumptions)
- known limitations (no dedicated audit trail in v1)
