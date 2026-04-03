import {afterAll, beforeEach, describe, expect, it, vi} from 'vitest';
import {Command} from 'commander';

import {registerApprovalsCommands} from '../src/commands/approvals';
import {print} from '../src/output';

const originalFetch = global.fetch;

function mockOkResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {'content-type': 'application/json'},
  });
}

describe('approvals commands', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockResolvedValue(
      mockOkResponse({
        id: 'approval-1',
        job_id: 'job-1',
        tool_name: 'rest_caller',
        proposed_args: {},
        context_summary: null,
        status: 'approved',
        timeout_at: '2026-04-03T12:00:00Z',
        decision_at: '2026-04-03T11:55:00Z',
        created_at: '2026-04-03T11:50:00Z',
      }),
    ) as unknown as typeof fetch;
  });

  it('sends approved=true for approvals approve', async () => {
    const program = new Command();
    registerApprovalsCommands(program);

    await program.parseAsync([
      'node',
      '2brain',
      'approvals',
      'approve',
      '--approval-id',
      'approval-1',
      '--reviewer-id',
      'ops@example.com',
      '--base-url',
      'http://localhost:8000/api/v1',
      '--api-key',
      'sk-test',
      '--json',
    ]);

    const fetchSpy = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const body = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(body.approved).toBe(true);
    expect(body.reviewer_id).toBe('ops@example.com');
  });

  it('sends approved=false for approvals reject', async () => {
    const program = new Command();
    registerApprovalsCommands(program);

    await program.parseAsync([
      'node',
      '2brain',
      'approvals',
      'reject',
      '--approval-id',
      'approval-1',
      '--reviewer-id',
      'ops@example.com',
      '--reason',
      'Out of policy',
      '--base-url',
      'http://localhost:8000/api/v1',
      '--api-key',
      'sk-test',
      '--json',
    ]);

    const fetchSpy = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const body = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(body.approved).toBe(false);
    expect(body.reason).toBe('Out of policy');
  });
});

describe('output fallback', () => {
  it('falls back to json when stdout is not a tty', () => {
    const writeSpy = vi.spyOn(process.stdout, 'write').mockImplementation(() => true);
    Object.defineProperty(process.stdout, 'isTTY', {value: false, configurable: true});

    print({hello: 'world'}, 'text');

    expect(writeSpy).toHaveBeenCalled();
    const payload = String(writeSpy.mock.calls[0]?.[0]);
    expect(payload).toContain('"hello": "world"');
  });
});

afterAll(() => {
  global.fetch = originalFetch;
});
