import type {Command} from 'commander';
import {loadConfig, resolveProfile} from '../config.js';
import {ApiClient} from '../api/client.js';
import {print, printError} from '../output.js';

export function registerAgentsCommands(program: Command): void {
  const agentsCmd = program.command('agents').description('Manage available agent definitions');

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

  agentsCmd
    .command('create')
    .description('Create a new conversational agent definition')
    .requiredOption('--name <name>', 'Agent name (must be unique)')
    .requiredOption('--prompt-file <path>', 'Prompt file path in repository')
    .option('--model-alias <alias>', 'Model alias: default|fast|embedding', 'default')
    .option('--max-execution-seconds <seconds>', 'Execution timeout in seconds', '60')
    .option('--semantic-memory-enabled', 'Enable semantic memory for this agent')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output as JSON')
    .action(async (opts: {
      name: string;
      promptFile: string;
      modelAlias: 'default' | 'fast' | 'embedding';
      maxExecutionSeconds: string;
      semanticMemoryEnabled?: boolean;
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
        const response = await client.createAgent({
          name: opts.name,
          prompt_file: opts.promptFile,
          model_alias: opts.modelAlias,
          max_execution_seconds: Number(opts.maxExecutionSeconds),
          semantic_memory_enabled: opts.semanticMemoryEnabled ?? false,
        });

        if (opts.json) {
          print(response, 'json');
          return;
        }

        const agent = response.agent;
        print(
          `Created agent ${agent.name} (${agent.id}) | graph=${agent.graph_type} | model=${agent.model_alias}`,
          'text',
        );
      } catch (err) {
        printError(err instanceof Error ? err.message : String(err));
        process.exit(1);
      }
    });
}
