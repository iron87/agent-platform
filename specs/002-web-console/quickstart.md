# Quickstart: Web Console Feature

## Prerequisites
- Node.js 20+
- Existing backend/API stack available locally (see project README and infra compose)
- Access to an API key for local direct mode testing

## 1. Start backend dependencies
Use existing repository workflow to bring up API services and dependencies.

## 2. Install frontend dependencies
From repository root:

```bash
npm install
```

## 3. Run the console
From repository root:

```bash
npm run web:dev
```

Open: `http://localhost:5174`

## 4. Configure profile
- Create a profile in the left panel
- Use `direct` mode for local API key testing or `proxy` mode for backend-routed calls
- Select the created profile as active

## 5. Validate core workflows
- Health: run health check and inspect structured response
- Agents: list existing agents, create a new agent with prompt and tool selection
- Run/Replay: execute synchronous run and trace-based replay
- Session: send multi-turn messages in an agent-scoped conversation
- Jobs: submit async job and observe polling status updates
- Approvals: fetch pending approval details and submit approve/reject decision

## 6. Validate build and tests
From repository root:

```bash
npm run web:test
npm run web:typecheck
npm run web:build
```

## Final Validation Notes
- Checklist gate: `requirements.md` completed (16/16)
- Test suite: 15 tests passing (`tests/lib` + `tests/components`)
- Typecheck: passes (`tsc --noEmit`)
- Production build: passes (Vite bundle generated)
- Security posture confirmed in docs:
	- network-scoped operator access for v1
	- `proxy` mode for production preference
	- `direct` mode available for local/dev usage
