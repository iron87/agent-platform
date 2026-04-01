import type {Command} from 'commander';
import {loadConfig, resolveProfile} from '../config.js';
import {ApiClient} from '../api/client.js';
import {print, printError} from '../output.js';

export function registerJobsCommands(program: Command): void {
  const jobsCmd = program.command('jobs').description('Manage background jobs');

  jobsCmd
    .command('submit')
    .description('Submit a job for asynchronous processing')
    .requiredOption('--agent-id <id>', 'Agent ID')
    .requiredOption('--input <text>', 'Input text for the agent')
    .option('--session-id <id>', 'Session ID')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      agentId: string;
      input: string;
      sessionId?: string;
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
        const response = await client.submitJob({
          agent_id: opts.agentId,
          input: opts.input,
          session_id: opts.sessionId,
        });
        print(response, opts.json ? 'json' : 'text');
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });

  jobsCmd
    .command('status')
    .description('Get the current status of a job')
    .requiredOption('--job-id <id>', 'Job ID')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      jobId: string;
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
        const status = await client.getJob(opts.jobId);
        print(status, opts.json ? 'json' : 'text');
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });

  jobsCmd
    .command('wait')
    .description('Wait for a job to reach a terminal state')
    .requiredOption('--job-id <id>', 'Job ID')
    .option('--timeout <seconds>', 'Maximum wait time in seconds', '300')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      jobId: string;
      timeout: string;
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
        const status = await client.waitForJob(
          opts.jobId,
          profile.pollIntervalSeconds,
          Number(opts.timeout),
        );
        print(status, opts.json ? 'json' : 'text');
        if (status.status === 'failed') {
          process.exit(1);
        }
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });
}
