// serve.mjs -- a static file server for the page tests (screenshot.mjs,
// readme-screenshots.mjs): serves WWW_DIR on 127.0.0.1, like
// `python3 -m http.server` does locally, with the types the page needs.
// Optionally over https and under a path prefix, as a static host would
// publish the page (a directory's URL serves its index.html).
// MIT licence, like the rest of this repository.

import { createServer } from 'node:http';
import { createServer as createTlsServer } from 'node:https';
import { existsSync, readFileSync, realpathSync, statSync } from 'node:fs';
import { extname, isAbsolute, join, normalize, relative, resolve, sep } from 'node:path';

const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.wasm': 'application/wasm', '.json': 'application/json',
  '.ttf': 'font/ttf', '.txt': 'text/plain; charset=utf-8', '.png': 'image/png',
};

// Resolves to { server, url } once listening; url is the page.
//   prefix  the path the page is published under ('/' or '/a/b/')
//   tls     { key, cert } (PEM) to serve https
//   host    the host name in the returned url (the server listens on
//           127.0.0.1 whatever it is; map other names there in the browser)
export async function serve(www, port, { prefix = '/', tls = null, host = '127.0.0.1' } = {}) {
  const root = realpathSync(www);
  const contained = (file) => {
    const rel = relative(root, file);
    return rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel);
  };
  const handler = (req, res) => {
    let pathname;
    try { pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname); }
    catch { res.writeHead(400); res.end(); return; }
    if (!pathname.startsWith(prefix)) {
      res.writeHead(404);
      res.end();
      return;
    }
    const path = normalize(pathname.slice(prefix.length)).replace(/^\/+/, '').replace(/^\.$/, '');
    let file = resolve(root, path || 'index.html');
    if (!contained(file)) { res.writeHead(404); res.end(); return; }
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
    if (!existsSync(file) || !contained(realpathSync(file)) || !statSync(file).isFile()) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(readFileSync(file));
  };
  const server = tls ? createTlsServer(tls, handler) : createServer(handler);
  await new Promise((r) => server.listen(port, '127.0.0.1', r));
  const origin = `${tls ? 'https' : 'http'}://${host}:${port}`;
  return { server, url: prefix === '/' ? `${origin}/index.html` : `${origin}${prefix}` };
}
