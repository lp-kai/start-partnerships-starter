// OS-neutral Python runner for hooks: tries py -3 (Windows), python3, python. Forwards stdin and exit code.
const { spawnSync } = require('child_process');
const args = process.argv.slice(2);
const input = require('fs').readFileSync(0);
for (const [cmd, pre] of [['py', ['-3']], ['python3', []], ['python', []]]) {
  const r = spawnSync(cmd, [...pre, ...args], { input, encoding: 'utf8' });
  if (r.error) continue;
  if (r.stdout) process.stdout.write(r.stdout);
  if (r.stderr) process.stderr.write(r.stderr);
  process.exit(r.status ?? 0);
}
process.exit(0); // no python found: fail open, never block a session
