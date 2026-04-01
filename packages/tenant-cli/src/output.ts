export type OutputMode = 'text' | 'json';

export function print(value: unknown, mode: OutputMode): void {
  if (mode === 'json') {
    process.stdout.write(JSON.stringify(value, null, 2) + '\n');
  } else {
    if (typeof value === 'string') {
      process.stdout.write(value + '\n');
    } else {
      process.stdout.write(JSON.stringify(value, null, 2) + '\n');
    }
  }
}

export function printError(message: string): void {
  process.stderr.write(`Error: ${message}\n`);
}

export function isTTY(): boolean {
  return Boolean(process.stdout.isTTY);
}
