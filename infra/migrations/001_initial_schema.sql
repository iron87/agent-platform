CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    api_key_hash TEXT NOT NULL UNIQUE,
    approval_endpoint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS agent_definitions (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    model_alias TEXT NOT NULL CHECK (model_alias IN ('default', 'fast', 'embedding')),
    prompt_file TEXT NOT NULL,
    graph_type TEXT NOT NULL CHECK (graph_type IN ('conversational', 'tool_agent', 'batch_agent')),
    tools TEXT[] NOT NULL DEFAULT '{}',
    hitl_tools TEXT[] NOT NULL DEFAULT '{}',
    max_execution_seconds INTEGER NOT NULL DEFAULT 60 CHECK (max_execution_seconds > 0),
    semantic_memory_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    agent_id UUID NOT NULL REFERENCES agent_definitions(id) ON DELETE RESTRICT,
    session_id TEXT,
    input_payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'interrupted', 'completed', 'failed')),
    result JSONB,
    error TEXT,
    trace_id TEXT,
    rq_job_id TEXT UNIQUE,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    mode TEXT NOT NULL CHECK (mode IN ('sync', 'async', 'session')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_client_created_at
    ON jobs (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_status_open
    ON jobs (status)
    WHERE status NOT IN ('completed', 'failed');

CREATE TABLE IF NOT EXISTS approval_requests (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    tool_name TEXT NOT NULL,
    proposed_args JSONB NOT NULL,
    context_summary TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'timed_out')),
    timeout_at TIMESTAMPTZ NOT NULL,
    decision_at TIMESTAMPTZ,
    reviewer_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_status_timeout
    ON approval_requests (status, timeout_at);

CREATE TABLE IF NOT EXISTS tenant_policies (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    pii_rules_summary JSONB,
    blocked_categories TEXT[] NOT NULL DEFAULT '{}',
    injection_detection_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    colang_hash TEXT,
    last_loaded_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
