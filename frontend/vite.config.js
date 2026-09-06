import { defineConfig } from "vite";
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8766",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (request) =>
            request.setHeader("Origin", "http://127.0.0.1:8766"),
          );
        },
      },
      "/projects": { target: "http://127.0.0.1:8766", changeOrigin: true },
    },
  },
});
