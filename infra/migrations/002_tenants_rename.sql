DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'clients'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'tenants'
    ) THEN
        ALTER TABLE clients RENAME TO tenants;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'client_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE jobs RENAME COLUMN client_id TO tenant_id;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'approval_requests' AND column_name = 'client_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'approval_requests' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE approval_requests RENAME COLUMN client_id TO tenant_id;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'client_policies'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'tenant_policies'
    ) THEN
        ALTER TABLE client_policies RENAME TO tenant_policies;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenant_policies' AND column_name = 'client_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenant_policies' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE tenant_policies RENAME COLUMN client_id TO tenant_id;
    END IF;
END $$;

DROP INDEX IF EXISTS idx_jobs_client_created_at;
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_created_at
    ON jobs (tenant_id, created_at DESC);
