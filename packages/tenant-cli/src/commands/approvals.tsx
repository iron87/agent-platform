import type {Command} from 'commander';
import {loadConfig, resolveProfile} from '../config.js';
import {ApiClient} from '../api/client.js';
import {print, printError} from '../output.js';

interface SharedApprovalOpts {
  approvalId: string;
  reviewerId: string;
  reason?: string;
  profile: string;
  baseUrl?: string;
  apiKey?: string;
  json?: boolean;
}

async function runDecision(
  opts: SharedApprovalOpts,
  approved: boolean,
): Promise<void> {
  const config = loadConfig();
  const profile = resolveProfile(config, {
    profileName: opts.profile,
    baseUrl: opts.baseUrl,
    apiKey: opts.apiKey,
    outputMode: opts.json ? 'json' : undefined,
  });

  const client = new ApiClient(profile.baseUrl, profile.apiKey);
  const result = await client.decideApproval(opts.approvalId, {
    approved,
    reviewer_id: opts.reviewerId,
    ...(opts.reason !== undefined ? {reason: opts.reason} : {}),
  });
  print(result, opts.json ? 'json' : 'text');
}

export function registerApprovalsCommands(program: Command): void {
  const approvalsCmd = program.command('approvals').description('Manage human-in-the-loop approvals');

  approvalsCmd
    .command('get')
    .description('Get details of a pending approval')
    .requiredOption('--approval-id <id>', 'Approval ID')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      approvalId: string;
      profile: string;
      baseUrl?: string;
      apiKey?: string;
      json?: boolean;
    }) => {
      const config = loadConfig();
      const profile = resolveProfile(config, {
        profileName: opts.profile,
        baseUrl: opts.baseUrl,
        apiKey: opts.apiKey,
        outputMode: opts.json ? 'json' : undefined,
      });

      const client = new ApiClient(profile.baseUrl, profile.apiKey);
      try {
        const approval = await client.getApproval(opts.approvalId);
        print(approval, opts.json ? 'json' : 'text');
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });

  approvalsCmd
    .command('decide')
    .description('Approve or reject a pending tool call (legacy alias; prefer approve/reject)')
    .requiredOption('--approval-id <id>', 'Approval ID')
    .requiredOption('--reviewer-id <id>', 'Reviewer identity')
    .option('--approve', 'Approve the tool call (default: reject)')
    .option('--reason <text>', 'Optional reason for the decision')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      approvalId: string;
      reviewerId: string;
      approve?: boolean;
      reason?: string;
      profile: string;
      baseUrl?: string;
      apiKey?: string;
      json?: boolean;
    }) => {
      try {
        await runDecision(
          {
            approvalId: opts.approvalId,
            reviewerId: opts.reviewerId,
            reason: opts.reason,
            profile: opts.profile,
            baseUrl: opts.baseUrl,
            apiKey: opts.apiKey,
            json: opts.json,
          },
          opts.approve ?? false,
        );
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });

  approvalsCmd
    .command('approve')
    .description('Approve a pending tool call')
    .requiredOption('--approval-id <id>', 'Approval ID')
    .requiredOption('--reviewer-id <id>', 'Reviewer identity')
    .option('--reason <text>', 'Optional reason note')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: SharedApprovalOpts) => {
      try {
        await runDecision(opts, true);
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });

  approvalsCmd
    .command('reject')
    .description('Reject a pending tool call')
    .requiredOption('--approval-id <id>', 'Approval ID')
    .requiredOption('--reviewer-id <id>', 'Reviewer identity')
    .option('--reason <text>', 'Reason for rejection')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: SharedApprovalOpts) => {
      try {
        await runDecision(opts, false);
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });
}
