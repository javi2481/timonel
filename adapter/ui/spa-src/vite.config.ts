import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// SPA — única UI del producto. Monta bajo /app/; build sin Node en el
// host de runtime (Docker corre vite build en el stage node, ver
// adapter/Dockerfile). outDir → adapter/ui/spa/, servido por FastAPI.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "../spa",
    emptyOutDir: true,
  },
});
