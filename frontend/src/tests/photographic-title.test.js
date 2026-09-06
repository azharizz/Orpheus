import { test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

test("photographic title renders three plates, fixed letters, and a tracking gate", async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { PhotographicTitle } = await server.ssrLoadModule("/src/app/photographic-title.jsx");
    const html = renderToStaticMarkup(React.createElement(PhotographicTitle, { paused: true }));
    assert.match(html, /<h1[^>]*>ORPHEUS<\/h1>/);
    assert.match(html, /data-paused="true"/);
    assert.equal((html.match(/class="title-scene"/g) || []).length, 3);
    assert.equal((html.match(/class="title-gate"/g) || []).length, 3);
    assert.match(html, /hero-microphone/);
    assert.doesNotMatch(html, /<button|shutter-blade/);
  } finally {
    await server.close();
  }
});
