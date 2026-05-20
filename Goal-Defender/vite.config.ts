import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const rawPort = process.env.PORT ?? "5173";
const port = Number(rawPort);

export default defineConfig({
  base: process.env.BASE_PATH ?? "/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
    },
    dedupe: ["react", "react-dom"],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
  },
  server: {
    port: Number.isNaN(port) || port <= 0 ? 5173 : port,
    host: "0.0.0.0",
    allowedHosts: true,
  },
  preview: {
    port: Number.isNaN(port) || port <= 0 ? 5173 : port,
    host: "0.0.0.0",
    allowedHosts: true,
  },
});
