import {createInterface} from 'readline';
import type {Command} from 'commander';
import React from 'react';
import {render, Text, Box} from 'ink';
import {loadConfig, resolveProfile} from '../config.js';
import {ApiClient} from '../api/client.js';
import {print, printError} from '../output.js';

interface ChatScreenProps {
  client: ApiClient;
  agentId: string;
  sessionId: string;
}

function ChatScreen({client, agentId, sessionId}: ChatScreenProps): React.ReactElement {
  const [messages, setMessages] = React.useState<Array<{role: 'user' | 'assistant'; text: string}>>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);

  React.useEffect(() => {
    const rl = createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    const ask = (): void => {
      rl.question('', (line) => {
        const input = line.trim();
        if (input === '/exit' || input === '/quit') {
          rl.close();
          setDone(true);
          return;
        }
        if (input === '') {
          ask();
          return;
        }
        setMessages((prev) => [...prev, {role: 'user', text: input}]);
        client
          .run({agent_id: agentId, input, session_id: sessionId})
          .then((response) => {
            setMessages((prev) => [...prev, {role: 'assistant', text: response.output}]);
            ask();
          })
          .catch((err: unknown) => {
            setError(err instanceof Error ? err.message : String(err));
            ask();
          });
      });
    };
    ask();

    return () => {
      rl.close();
    };
  }, []);

  if (done) {
    return <Text>Session ended.</Text>;
  }

  return (
    <Box flexDirection="column">
      {messages.map((m, i) => (
        <Box key={i}>
          <Text color={m.role === 'user' ? 'cyan' : 'green'}>
            [{m.role}] {m.text}
          </Text>
        </Box>
      ))}
      {error !== null && <Text color="red">Error: {error}</Text>}
      <Text dimColor>Type /exit to quit</Text>
    </Box>
  );
}

export function registerRunCommands(program: Command): void {
  program
    .command('run')
    .description('Run an agent and wait for the response')
    .requiredOption('--agent-id <id>', 'Agent ID to invoke')
    .requiredOption('--input <text>', 'Input text for the agent')
    .option('--session-id <id>', 'Session ID for conversation continuity')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .option('--json', 'Output response as JSON')
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
        const response = await client.run({
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
}

export function registerChatCommands(program: Command): void {
  const sessionCmd = program.command('session').description('Manage interactive sessions');

  sessionCmd
    .command('chat')
    .description('Start an interactive chat session with an agent')
    .requiredOption('--agent-id <id>', 'Agent ID')
    .requiredOption('--session-id <id>', 'Session ID')
    .option('--profile <name>', 'Config profile', 'default')
    .option('--base-url <url>', 'Override API base URL')
    .option('--api-key <key>', 'Override API key')
    .action(async (opts: {
      agentId: string;
      sessionId: string;
      profile: string;
      baseUrl?: string;
      apiKey?: string;
    }) => {
      const config = loadConfig();
      const profile = resolveProfile(config, {
        profileName: opts.profile,
        baseUrl: opts.baseUrl,
        apiKey: opts.apiKey,
      });

      const client = new ApiClient(profile.baseUrl, profile.apiKey);
      const {waitUntilExit} = render(
        <ChatScreen
          client={client}
          agentId={opts.agentId}
          sessionId={opts.sessionId}
        />,
      );
      await waitUntilExit();
    });
}
