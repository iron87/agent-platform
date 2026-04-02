import type {Command} from 'commander';
import {loadConfig, resolveProfile} from '../config.js';
import {ApiClient} from '../api/client.js';
import {print, printError} from '../output.js';

export function registerAgentsCommands(program: Command): void {
  const agentsCmd = program.command('agents').description('List available agent definitions');

  agentsCmd
    .command('list')
    .description('List agent definitions visible to the current tenant')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
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
        const response = await client.listAgents();
        if (opts.json) {
          print(response, 'json');
          return;
        }

        if (response.agents.length === 0) {
          print('No agent definitions found for this tenant.', 'text');
          return;
        }

        const lines = response.agents.map(
          (agent) =>
            `${agent.id} | ${agent.name} | graph=${agent.graph_type} | model=${agent.model_alias} | v${agent.version}`,
        );
        print(lines.join('\n'), 'text');
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });
}
