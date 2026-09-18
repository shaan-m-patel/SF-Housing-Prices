# SF Rent Atlas (web)

Static Next.js app for the rent estimator and map. All data comes from `public/data/`, which
`uv run sfrent build` (in the repo root) regenerates and mirrors from `data/public/`.

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # static export in out/
npm run typecheck && npm run lint
```

- `app/` layout, page, theme (`globals.css`), favicon
- `components/explorer.tsx` holds all UI state; `estimate-*` and `unit-form` are the calculator,
  `rent-map*` and `map-controls` the MapLibre view, `*-card` the charts and ranking
- `lib/model.ts` mirrors `sfrent.model.predict`; `lib/geo.ts` has the haversine/H3 helpers
- `scripts/copy-maplibre-worker.mjs` copies MapLibre's web worker into `public/maplibre/` before
  dev/build (the bundled worker URL does not resolve)

Basemap tiles are served by [OpenFreeMap](https://openfreemap.org) (no key). Deployed on Vercel
with this directory as the project root.
