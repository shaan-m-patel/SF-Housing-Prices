"use client";

import { useMemo, useState } from "react";
import { DistanceCard } from "@/components/distance-card";
import { EstimateCard } from "@/components/estimate-card";
import type { MapLayer } from "@/components/map-controls";
import { MethodNote } from "@/components/method-note";
import { RankingCard } from "@/components/ranking-card";
import { RentMap } from "@/components/rent-map";
import { TrendCard } from "@/components/trend-card";
import { statsFor, type AppData } from "@/lib/data";
import { hexFeatures, weightedMedian, type LatLng } from "@/lib/geo";
import { estimate, type Unit } from "@/lib/model";

const DEFAULT_UNIT: Unit = {
  neighborhood: "Mission",
  bedrooms: 2,
  bathrooms: 1,
  sqft: 900,
  yearBuilt: "1920_1945",
  buildingUnits: "5_19",
};

export function Explorer({ data }: { data: AppData }) {
  const [unit, setUnit] = useState<Unit>(() =>
    data.model.neighborhoods[DEFAULT_UNIT.neighborhood]
      ? DEFAULT_UNIT
      : { ...DEFAULT_UNIT, neighborhood: Object.keys(data.model.neighborhoods).sort()[0] },
  );
  const [layer, setLayer] = useState<MapLayer>("neighborhoods");
  const [work, setWork] = useState<LatLng | null>(null);
  const [radiusKm, setRadiusKm] = useState(3);
  const [placing, setPlacing] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  const statsByHood = useMemo(() => statsFor(data.stats, unit.bedrooms), [data.stats, unit.bedrooms]);
  const cityMedian = data.summary.citywide[String(Math.min(unit.bedrooms, 4))]?.rent_median ?? null;
  const result = useMemo(() => estimate(data.model, unit), [data.model, unit]);
  const hexes = useMemo(
    () => hexFeatures(data.hexes, unit.bedrooms, work, radiusKm),
    [data.hexes, unit.bedrooms, work, radiusKm],
  );
  const within = useMemo(() => {
    const inside = hexes.features.map((f) => f.properties).filter((p) => p.within && p.median !== null);
    return {
      hexes: work ? inside.length : 0,
      median: work ? weightedMedian(inside.map((p) => ({ median: p.median as number, n: p.n }))) : null,
    };
  }, [hexes, work]);

  const patchUnit = (patch: Partial<Unit>) => setUnit((u) => ({ ...u, ...patch }));
  const selectNeighborhood = (name: string) => {
    if (data.model.neighborhoods[name] !== undefined) patchUnit({ neighborhood: name });
  };

  return (
    <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 pt-4 pb-8 lg:px-6">
      <div className="grid gap-4 lg:grid-cols-[400px_minmax(0,1fr)]">
        <EstimateCard
          model={data.model}
          unit={unit}
          onChange={patchUnit}
          estimate={result}
          hoodStats={statsByHood.get(unit.neighborhood)}
          cityMedian={cityMedian}
          referenceMonth={data.summary.reference_month}
        />
        <div className="h-[560px] lg:h-auto lg:min-h-[680px]">
          <RentMap
            neighborhoods={data.neighborhoods}
            statsByHood={statsByHood}
            hexes={hexes}
            bedrooms={unit.bedrooms}
            layer={layer}
            onLayerChange={setLayer}
            selected={unit.neighborhood}
            onSelect={selectNeighborhood}
            hovered={hovered}
            onHover={setHovered}
            work={work}
            onWork={setWork}
            radiusKm={radiusKm}
            onRadius={setRadiusKm}
            placing={placing}
            onPlacing={setPlacing}
            within={within}
          />
        </div>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <DistanceCard
          hexes={hexes}
          work={work}
          radiusKm={radiusKm}
          bedrooms={unit.bedrooms}
          onStartPlacing={() => {
            setPlacing(true);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
        <RankingCard
          statsByHood={statsByHood}
          neighborhoods={data.neighborhoods}
          bedrooms={unit.bedrooms}
          selected={unit.neighborhood}
          hovered={hovered}
          work={work}
          onSelect={selectNeighborhood}
          onHover={setHovered}
        />
        <TrendCard zori={data.zori} />
      </div>
      <MethodNote summary={data.summary} />
    </main>
  );
}
