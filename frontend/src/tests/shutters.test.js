import { test } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

test("photographic title renders with both scenes and closed shutters", async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] } });
  try {
    const { Shutters } = await server.ssrLoadModule("/src/app/shutters.jsx");
    const html = renderToStaticMarkup(React.createElement(Shutters));
    assert.match(html, /<h1[^>]*>ORPHEUS<\/h1>/);
    assert.match(html, /data-open="false"/);
    assert.match(html, /aria-expanded="false"/);
    assert.match(html, /Footsteps/);
    assert.match(html, /Recording/);
  } finally {
    await server.close();
  }
});
