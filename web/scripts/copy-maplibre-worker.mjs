// MapLibre 6 loads its web worker from a URL next to its own module, which bundlers break.
// Copy the worker (and the shared chunk it imports) into public/ so we can point
// maplibregl.setWorkerUrl at a stable path. Runs before `next dev` / `next build`.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const dist = path.dirname(require.resolve("maplibre-gl/package.json")) + "/dist";
const target = path.join(import.meta.dirname, "..", "public", "maplibre");

mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(path.join(dist, file), path.join(target, file));
}
