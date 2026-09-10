/**
 * Local fake API + static server for the minimal Playwright browser path.
 *
 * It serves the built V2 artifact from web/dist under /ui-v2/ and fake
 * /api/v1/dashboard, /api/v1/system/status, /api/v1/file-index and
 * /api/v1/storage/files GET
 * documents that mirror the existing Python contracts. Every unsupported
 * method is rejected with 405; no production credentials, media, Storage or
 * external providers are involved, and no token material is ever logged.
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

const SYSTEM_STATUS = {
  system: {
    application_version: "2.0.0.dev0",
    configuration_valid: true,
    configuration_authority: "MANAGED",
    configuration_snapshot_id: "rev-e2e-1",
    configuration_snapshot_digest: "digest-e2e-1",
  },
  storages: {
    total: 2,
    truncated: false,
    items: [
      {
        id: "local-media",
        name: "Local media",
        type: "local",
        read_only: true,
      },
      {
        id: "remote-media",
        name: "Remote media",
        type: "openlist",
        read_only: false,
      },
    ],
  },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [{ id: "resources", storage_id: "local-media", enabled: true }],
  },
  media_libraries: { total: 1, truncated: false, items: [] },
  recognition_types: { total: 3, truncated: false, items: [] },
  recognition_rules: { total: 3, truncated: false, items: [] },
  recognition_type_policies: { total: 3, truncated: false, items: [] },
  metadata_policies: { total: 3, truncated: false, items: [] },
  naming_policies: { total: 3, truncated: false, items: [] },
  classification_policies: { total: 3, truncated: false, items: [] },
  organize_policies: { total: 3, truncated: false, items: [] },
};

const FILE_INDEX_ITEMS = [
  {
    fileId: "file-index-example",
    storageId: "local-media",
    resourceLibraryId: "resources",
    path: "Movies/Example.mkv",
    filename: "Example.mkv",
    extension: "mkv",
    size: 2097152000,
    modifiedAt: "2026-08-22T12:10:00+00:00",
    updatedAt: "2026-08-22T12:10:00+00:00",
    firstSeenAt: "2026-08-22T11:10:00+00:00",
    lastSeenAt: "2026-08-22T12:10:00+00:00",
    stableSince: "2026-08-22T11:30:00+00:00",
    missingSince: null,
    scanStatus: "ready",
    change: "unchanged",
    occurrenceState: "verified",
    currentOccurrence: { state: "verified", current: true },
    processingDisposition: "organized",
    recognitionType: "Movie",
    provider: "tmdb",
    providerId: "101",
    title: "Example",
    year: "2026",
    taskId: "task-example",
    identitySummary: {
      recognitionType: "Movie",
      provider: "tmdb",
      providerId: "101",
      title: "Example",
      year: 2026,
    },
  },
  ...Array.from({ length: 151 }, (_, index) => {
    const number = String(index + 1).padStart(3, "0");
    const dispositions = ["organized", "attention", "unknown"];
    const statuses = ["ready", "unstable", "discovered"];
    return {
      fileId: `file-index-${number}`,
      storageId: "local-media",
      resourceLibraryId: "resources",
      path: `Movies/Title-${number}.mkv`,
      filename: `Title-${number}.mkv`,
      extension: "mkv",
      size: 1048576 + index,
      modifiedAt: "2026-08-22T12:00:00+00:00",
      updatedAt: "2026-08-22T12:00:00+00:00",
      firstSeenAt: "2026-08-22T11:00:00+00:00",
      lastSeenAt: "2026-08-22T12:00:00+00:00",
      stableSince: index % 2 === 0 ? "2026-08-22T11:30:00+00:00" : null,
      missingSince: null,
      scanStatus: statuses[index % statuses.length],
      change: index % 2 === 0 ? "unchanged" : "modified",
      occurrenceState: index % 3 === 0 ? "verified" : "unverified",
      currentOccurrence: {
        state: index % 3 === 0 ? "verified" : "unverified",
        current: true,
      },
      processingDisposition: dispositions[index % dispositions.length],
      recognitionType: index % 2 === 0 ? "Movie" : "TV",
      provider: "tmdb",
      providerId: String(200 + index),
      title: `Title ${number}`,
      year: String(2000 + (index % 25)),
      taskId: `task-${number}`,
      identitySummary:
        index % 2 === 0
          ? {
              recognitionType: index % 2 === 0 ? "Movie" : "TV",
              provider: "tmdb",
              providerId: String(200 + index),
              title: `Title ${number}`,
              year: 2000 + (index % 25),
            }
          : null,
    };
  }),
];

const FILE_INDEX_ALLOWED_QUERY = new Set([
  "resourceLibrary",
  "storage",
  "scanStatus",
  "query",
  "limit",
  "after",
  "before",
  "cursorFileId",
  "recognitionType",
  "provider",
  "providerId",
  "title",
  "taskId",
  "year",
  "processingDisposition",
]);

const FILE_INDEX_SCAN_STATUSES = new Set([
  "discovered",
  "unstable",
  "ready",
  "ignored",
  "missing",
  "error",
]);

const FILE_INDEX_PROCESSING_DISPOSITIONS = new Set([
  "unknown",
  "organized",
  "skipped",
  "attention",
  "conflict",
  "review",
  "partial",
  "failed",
  "unverified",
  "reprocess_requested",
]);

function fileIndexTuple(item) {
  return [Date.parse(item.updatedAt), item.fileId];
}

function compareFileIndexTuples(left, right) {
  const [leftTime, leftId] = fileIndexTuple(left);
  const [rightTime, rightId] = fileIndexTuple(right);
  if (leftTime !== rightTime) return leftTime - rightTime;
  return leftId.localeCompare(rightId);
}

function fileIndexCursor(url, timestampKey) {
  const timestamp = url.searchParams.get(timestampKey);
  if (timestamp === null) return null;
  const fileId = url.searchParams.get("cursorFileId");
  if ((timestamp === null) !== (fileId === null)) {
    return { error: "cursor" };
  }
  if (timestamp === null || fileId === null) return null;
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed) || fileId.length === 0) {
    return { error: "cursor" };
  }
  return { updatedAt: new Date(parsed).toISOString(), fileId };
}

function fileIndexDocument(url) {
  const values = new Map();
  for (const [key, value] of url.searchParams.entries()) {
    if (!FILE_INDEX_ALLOWED_QUERY.has(key) || values.has(key)) {
      return { status: 400, payload: { error: { code: "invalid_filter" } } };
    }
    values.set(key, value);
  }
  const limit = Number(values.get("limit") ?? "100");
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (
    values.has("scanStatus") &&
    !FILE_INDEX_SCAN_STATUSES.has(values.get("scanStatus"))
  ) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (
    values.has("processingDisposition") &&
    !FILE_INDEX_PROCESSING_DISPOSITIONS.has(values.get("processingDisposition"))
  ) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (values.has("after") && values.has("before")) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  if (
    values.has("cursorFileId") &&
    !values.has("after") &&
    !values.has("before")
  ) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  const after = fileIndexCursor(url, "after");
  const before = fileIndexCursor(url, "before");
  if (after?.error || before?.error) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  const query = (values.get("query") ?? "").toLowerCase();
  const items = FILE_INDEX_ITEMS.filter((item) => {
    if (
      values.has("resourceLibrary") &&
      item.resourceLibraryId !== values.get("resourceLibrary")
    ) {
      return false;
    }
    if (values.has("storage") && item.storageId !== values.get("storage")) {
      return false;
    }
    if (
      values.has("scanStatus") &&
      item.scanStatus !== values.get("scanStatus")
    ) {
      return false;
    }
    if (
      values.has("processingDisposition") &&
      item.processingDisposition !== values.get("processingDisposition")
    ) {
      return false;
    }
    if (
      query !== "" &&
      !item.path.toLowerCase().includes(query) &&
      !item.filename.toLowerCase().includes(query)
    ) {
      return false;
    }
    if (
      values.has("recognitionType") &&
      item.recognitionType !== values.get("recognitionType")
    ) {
      return false;
    }
    if (values.has("provider") && item.provider !== values.get("provider")) {
      return false;
    }
    if (
      values.has("providerId") &&
      item.providerId !== values.get("providerId")
    ) {
      return false;
    }
    if (
      values.has("title") &&
      !item.title.toLowerCase().includes(values.get("title").toLowerCase())
    ) {
      return false;
    }
    if (values.has("taskId") && item.taskId !== values.get("taskId")) {
      return false;
    }
    if (values.has("year") && item.year !== values.get("year")) {
      return false;
    }
    if (after && compareFileIndexTuples(item, after) >= 0) {
      return false;
    }
    if (before && compareFileIndexTuples(item, before) <= 0) {
      return false;
    }
    return true;
  }).sort((left, right) => compareFileIndexTuples(right, left));
  const pageItems = before ? items.slice(-limit) : items.slice(0, limit);
  return {
    status: 200,
    payload: {
      surface: "file_index",
      fileIndexSurface: "/api/v1/file-index",
      filesSurface: "/api/v1/storage/files",
      items: pageItems,
      limit,
    },
  };
}

function filesDocument(path, cursor, storageId) {
  const storage =
    storageId === "remote-media"
      ? { id: "remote-media", name: "Remote media", type: "openlist" }
      : { id: "local-media", name: "Local media", type: "local" };
  const isRoot = path === "";
  const segments = path === "" ? [] : path.split("/");
  const breadcrumbs = [
    { name: "Storage root", path: "", isRoot: true },
    ...segments.map((segment, index) => ({
      name: segment,
      path: segments.slice(0, index + 1).join("/"),
      isRoot: false,
    })),
  ];
  const entries =
    storage.id === "remote-media"
      ? isRoot
        ? [
            {
              name: "remote.mkv",
              path: "remote.mkv",
              type: "file",
              entryType: "file",
              size: 1024,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
          ]
        : []
      : isRoot
        ? [
            {
              name: "movies",
              path: "movies",
              type: "directory",
              entryType: "directory",
              size: 0,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: true,
              isSymlink: false,
              traversable: true,
              selectable: true,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
            {
              name: "show.mkv",
              path: "show.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [{ fileId: "file-e2e-1" }],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "draft.mkv",
              path: "draft.mkv",
              type: "file",
              entryType: "file",
              size: 524288000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
          ]
        : path === "movies"
          ? [
              {
                name: "movie.mkv",
                path: "movies/movie.mkv",
                type: "file",
                entryType: "file",
                size: 2097152000,
                modifiedAt: "2026-08-22T12:00:00+00:00",
                isDirectory: false,
                isSymlink: false,
                traversable: false,
                selectable: false,
                indexMembership: {
                  available: false,
                  indexed: false,
                  memberships: [],
                  total: 0,
                  truncated: false,
                },
              },
            ]
          : [];
  const hasNext =
    storage.id === "local-media" && (path === "" || Boolean(cursor));
  return {
    revisionId: "rev-e2e-1",
    revision: { revisionId: "rev-e2e-1", version: 1, digest: "digest-e2e-1" },
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-e2e-1",
      version: 1,
      digest: "digest-e2e-1",
    },
    storage,
    storageId: storage.id,
    storageName: storage.name,
    storageType: storage.type,
    pathScope: "storage_relative",
    root: "",
    rootPath: "",
    canonicalPath: path,
    path,
    breadcrumbs,
    entries,
    limit: 50,
    nextCursor: hasNext ? "cursor-page-2" : null,
    hasNext,
    exhausted: !hasNext,
    continuation: {
      hasNext,
      exhausted: !hasNext,
      cursorBoundTo: "revision/storage/path/limit",
    },
    sideEffects: "none",
    retrySafe: true,
  };
}

function bearerToken(req) {
  const header = req.headers.authorization ?? "";
  return header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
}

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

const CONTENT_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const token = bearerToken(req);

  if (url.pathname === "/api/v1/dashboard") {
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
  if (url.pathname === "/api/v1/system/status") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
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
    sendJson(res, 200, SYSTEM_STATUS);
    return;
  }
  if (url.pathname === "/api/v1/file-index") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const document = fileIndexDocument(url);
    sendJson(res, document.status, document.payload);
    return;
  }
  if (url.pathname === "/api/v1/storage/files") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
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
    const storageId = url.searchParams.get("storageId");
    if (!["local-media", "remote-media"].includes(storageId)) {
      sendJson(res, 404, {
        error: {
          code: "storage_browser_storage_not_found",
          message: "configured Storage was not found",
          details: {
            category: "storage_not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "reload the configuration revision and choose one configured Storage",
          },
        },
      });
      return;
    }
    const path = url.searchParams.get("path") ?? "";
    if (path.includes("..") || path.startsWith("/") || path.includes("\\")) {
      sendJson(res, 400, {
        error: {
          code: "storage_browser_invalid_path",
          message: "Storage-relative path is invalid",
          details: {
            category: "invalid_path",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "use the displayed Storage-relative breadcrumb or enter a safe relative path",
          },
        },
      });
      return;
    }
    if (path === "missing") {
      sendJson(res, 404, {
        error: {
          code: "storage_browser_not_found",
          message: "Storage directory was not found",
          details: {
            category: "not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "make the configured directory available, reload, and retry",
          },
        },
      });
      return;
    }
    if (path === "blocked") {
      sendJson(res, 403, {
        error: {
          code: "storage_browser_permission_denied",
          message: "Storage read permission was denied",
          details: {
            category: "permission_denied",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "grant MediaFlow read/list permission, reload, and retry",
          },
        },
      });
      return;
    }
    // No Active runtime fixture
    if (
      url.searchParams.has("fixture") &&
      url.searchParams.get("fixture") === "no-active"
    ) {
      sendJson(res, 200, {
        system: {
          application_version: "2.0.0.dev0",
          configuration_valid: false,
          configuration_authority: null,
        },
        storages: { total: 0, truncated: false, items: [] },
        resource_libraries: { total: 0, truncated: false, items: [] },
      });
      return;
    }
    // Invalid/stale cursor fixture
    const cursor = url.searchParams.get("cursor");
    if (cursor === "stale-cursor") {
      sendJson(res, 400, {
        error: {
          code: "storage_browser_cursor_invalid",
          message: "page continuation is no longer valid",
          details: {
            category: "cursor_invalid",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "reload the current revision and restart browsing from the directory root",
          },
        },
      });
      return;
    }
    sendJson(res, 200, filesDocument(path, cursor, storageId));
    return;
  }
  if (req.method !== "GET") {
    res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("GET required");
    return;
  }
  if (url.pathname === "/ui") {
    const body = Buffer.from(`<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>MediaFlow V1 Web UI</title></head>
  <body><main><h1>MediaFlow V1 Web UI</h1><p>Current Web continuation.</p></main></body>
</html>`);
    sendFile(res, body, CONTENT_TYPES[".html"]);
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
