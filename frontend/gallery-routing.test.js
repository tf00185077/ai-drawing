// @vitest-environment node
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer as createHttpServer } from "node:http";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "vite";
import config from "./vite.config.js";

// Synthetic upstream only: no real Backend lifespan/state or generation.
let upstream, vite, root, origin;
const asset = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
beforeAll(async () => {
  upstream = createHttpServer((req, res) => {
    if (req.url === "/api/gallery/?limit=20") {
      res.setHeader("Content-Type", "application/json");
      res.end('{"items":[],"total":0}');
    } else if (req.url === "/gallery/2026-08-06/original.png") {
      res.setHeader("Content-Type", "image/png"); res.end(asset);
    } else if (req.url === "/gallery") {
      res.writeHead(307, { Location: "/gallery/" }); res.end();
    } else { res.writeHead(404); res.end("not found"); }
  });
  await new Promise(resolve => upstream.listen(0, "127.0.0.1", resolve));
  root = await mkdtemp(join(process.env.TMPDIR || tmpdir(), "gallery-routing-"));
  await writeFile(join(root, "index.html"), '<div id="root">Gallery SPA fixture</div>');
  const target = `http://127.0.0.1:${upstream.address().port}`;
  const proxy = Object.fromEntries(Object.entries(config.server.proxy).map(([key, value]) => [key, { ...value, target }]));
  vite = await createServer({ ...config, plugins: [], configFile: false, root, cacheDir: join(root, "cache"), server: { host: "127.0.0.1", port: 0, proxy } });
  await vite.listen();
  origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
});
afterAll(async () => {
  await vite?.close();
  if (upstream) await new Promise(resolve => upstream.close(resolve));
  if (root) await rm(root, { recursive: true, force: true });
});
describe("Gallery document and asset routing", () => {
  it.each(["/gallery", "/gallery/", "/gallery?from_date=2026-08-06", "/gallery/?from_date=2026-08-06"])("serves the SPA document at %s without redirect", async path => {
    const res = await fetch(origin + path, { headers: { Accept: "text/html" }, redirect: "manual" });
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    expect(await res.text()).toContain("Gallery SPA fixture");
  });
  it("keeps original asset bytes on the Gallery proxy", async () => {
    const res = await fetch(origin + "/gallery/2026-08-06/original.png");
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/png");
    expect(Buffer.from(await res.arrayBuffer())).toEqual(asset);
  });
  it("keeps API requests on the Backend proxy", async () => {
    const res = await fetch(origin + "/api/gallery/?limit=20");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ items: [], total: 0 });
  });
});
