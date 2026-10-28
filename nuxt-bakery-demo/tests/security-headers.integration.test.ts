import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:net';
import test from 'node:test';

const requiredDirectives = [
  'default-src',
  'script-src',
  'script-src-attr',
  'style-src',
  'style-src-attr',
  'img-src',
  'connect-src',
  'font-src',
  'frame-src',
  'media-src',
  'manifest-src',
  'worker-src',
  'form-action',
  'object-src',
  'base-uri',
  'frame-ancestors',
] as const;

async function getAvailablePort(): Promise<number> {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert(address && typeof address !== 'string');
  server.close();
  await once(server, 'close');
  return address.port;
}

async function waitForServer(url: string, process: ChildProcess): Promise<void> {
  const deadline = Date.now() + 20_000;

  while (Date.now() < deadline) {
    if (process.exitCode !== null) {
      throw new Error(`Nitro exited before becoming ready (${process.exitCode})`);
    }

    try {
      const response = await fetch(url, { redirect: 'manual' });
      if (response.status > 0) return;
    } catch {
      // The TCP listener is not ready yet.
    }

    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  throw new Error('Timed out waiting for the built Nitro server');
}

function getNonce(csp: string): string {
  const match = csp.match(/'nonce-([^']+)'/);
  assert(match, `CSP does not contain a nonce: ${csp}`);
  return match[1];
}

function assertSecurityHeaders(response: Response): string {
  const csp = response.headers.get('content-security-policy');
  assert(csp, 'Content-Security-Policy header is required');
  assert.equal(response.headers.get('x-frame-options'), 'SAMEORIGIN');

  for (const directive of requiredDirectives) {
    assert.match(csp, new RegExp(`(?:^|;\\s*)${directive}(?:\\s|;|$)`));
  }

  assert.doesNotMatch(csp, /'unsafe-inline'/);
  return getNonce(csp);
}

function assertInlineElementsUseNonce(html: string, nonce: string): void {
  const inlineElements = [
    ...html.matchAll(/<(script|style)\b([^>]*)>([\s\S]*?)<\/\1>/gi),
  ].filter((match) => {
    const attributes = match[2];
    return match[1].toLowerCase() === 'style' || !/\bsrc\s*=/.test(attributes);
  });

  assert(inlineElements.length > 0, 'Expected generated inline elements');
  for (const element of inlineElements) {
    const attributes = element[2];
    assert(
      attributes.includes(`nonce="${nonce}"`) ||
        attributes.includes(`nonce='${nonce}'`),
      `Inline ${element[1]} is missing the response nonce`,
    );
  }
}

test('built Nuxt responses enforce a unique nonce-based strict CSP', async () => {
  const port = await getAvailablePort();
  const origin = `http://127.0.0.1:${port}`;
  let output = '';
  const server = spawn(process.execPath, ['.output/server/index.mjs'], {
    cwd: new URL('..', import.meta.url),
    env: {
      ...process.env,
      NITRO_HOST: '127.0.0.1',
      NITRO_PORT: String(port),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout?.on('data', (chunk) => {
    output += chunk.toString();
  });
  server.stderr?.on('data', (chunk) => {
    output += chunk.toString();
  });

  try {
    await waitForServer(`${origin}/en/`, server);

    const rootResponse = await fetch(`${origin}/`, { redirect: 'manual' });
    assert.equal(rootResponse.status, 301);
    assertSecurityHeaders(rootResponse);

    const firstResponse = await fetch(`${origin}/en/`);
    assert.equal(firstResponse.status, 200);
    const firstNonce = assertSecurityHeaders(firstResponse);
    assertInlineElementsUseNonce(await firstResponse.text(), firstNonce);

    const secondResponse = await fetch(`${origin}/en/`);
    const secondNonce = assertSecurityHeaders(secondResponse);
    assert.notEqual(secondNonce, firstNonce);
  } catch (error) {
    throw new Error(`${String(error)}\nNitro output:\n${output}`);
  } finally {
    server.kill();
    if (server.exitCode === null) await once(server, 'exit');
  }
});
