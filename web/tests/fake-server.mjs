/**
 * Local fake API + static server for the minimal Playwright browser path.
 *
 * It serves the built V2 artifact from web/dist under /ui-v2/ and a tiny
 * fake /api/v1/dashboard that mirrors the existing Python contract. No
 * production credentials, media, Storage or external providers are involved,
 * and no token material is ever logged.
 */

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HOST = "127.0.0.1";
const PORT = Number(process.env.FAKE_PORT ?? 4173);
const DIST = fileURLToPath(new URL("../dist", import.meta.url));

const VIEWER_TOKENS = new Set(["e2e-viewer-token"]);
const LIMITED_TOKENS = new Set(["e2e-limited-token"]);
const EXPIRED_TOKENS = new Set(["e2e-expired-token"]);

const DASHBOARD_SNAPSHOT = {
  as_of: "2026-08-22T12:00:00+00:00",
  resource_libraries: 1,
  media_libraries: 1,
  files: { total: 12, ready: 9, unstable: 1, missing: 1, errors: 1 },
  tasks: {
    total: 4,
    pending: 1,
    running: 1,
    completed: 1,
    partial_success: 0,
    failed: 1,
    cancelled: 0,
    paused: 0,
  },
  jobs: {
    total: 2,
    pending: 1,
    running: 0,
    completed: 1,
    failed: 0,
    cancelled: 0,
  },
  pending_confirmations: 0,
  pending_metadata_reviews: 1,
  pending_classification_reviews: 0,
  dead_letter_notifications: 0,
  recent_failures: [
    {
      kind: "job",
      identifier: "job-e2e-1",
      status: "failed",
      occurred_at: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
  ],
};

const CONTENT_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
};

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(body);
}

function sendFile(res, body, contentType) {
  res.writeHead(200, {
    "Content-Type": contentType,
    "Content-Length": body.length,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(body);
}

async function readArtifact(path) {
  const resolved = normalize(join(DIST, path));
  if (!resolved.startsWith(normalize(DIST + sep))) {
    return null;
  }
  try {
    return await readFile(resolved);
  } catch {
    return null;
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  if (url.pathname === "/api/v1/dashboard") {
    const header = req.headers.authorization ?? "";
    const token = header.startsWith("Bearer ")
      ? header.slice("Bearer ".length)
      : "";
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    sendJson(res, 200, DASHBOARD_SNAPSHOT);
    return;
  }
  if (req.method !== "GET") {
    res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("GET required");
    return;
  }
  if (url.pathname === "/ui-v2" || url.pathname === "/ui-v2/") {
    const index = await readArtifact("index.html");
    if (index === null) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("V2 artifact is not built; run npm --prefix web run build");
      return;
    }
    sendFile(res, index, CONTENT_TYPES[".html"]);
    return;
  }
  if (url.pathname.startsWith("/ui-v2/")) {
    const relative = url.pathname.slice("/ui-v2/".length);
    const hasFileSuffix = Boolean(extname(relative));
    const body = await readArtifact(relative);
    if (body !== null && Object.hasOwn(CONTENT_TYPES, extname(relative))) {
      sendFile(res, body, CONTENT_TYPES[extname(relative)]);
      return;
    }
    if (hasFileSuffix) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("not found");
      return;
    }
    const index = await readArtifact("index.html");
    if (index === null) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("V2 artifact is not built; run npm --prefix web run build");
      return;
    }
    sendFile(res, index, CONTENT_TYPES[".html"]);
    return;
  }
  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  res.end("not found");
});

server.listen(PORT, HOST, () => {
  console.log(`fake V2 server listening on http://${HOST}:${PORT}/ui-v2/`);
});
