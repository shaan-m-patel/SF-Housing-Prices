"use client";

import type { FeatureCollection, Polygon } from "geojson";
import { BriefcaseBusiness } from "lucide-react";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { bedroomLabel } from "@/lib/data";
import { usd, usdCompact } from "@/lib/format";
import { DISTANCE_BANDS_KM, bandLabel, weightedMedian, type HexProps, type LatLng } from "@/lib/geo";

type Props = {
  hexes: FeatureCollection<Polygon, HexProps>;
  work: LatLng | null;
  radiusKm: number;
  bedrooms: number;
  onStartPlacing: () => void;
};

const config = { median: { label: "Median rent", color: "var(--chart-1)" } } satisfies ChartConfig;

export function DistanceCard({ hexes, work, radiusKm, bedrooms, onStartPlacing }: Props) {
  const rows = useMemo(() => {
    if (!work) return [];
    return DISTANCE_BANDS_KM.map((band) => {
      const cells = hexes.features
        .map((f) => f.properties)
        .filter((p) => p.median !== null && p.distanceKm !== null && p.distanceKm >= band[0] && p.distanceKm < band[1])
        .map((p) => ({ median: p.median as number, n: p.n }));
      return {
        band: bandLabel(band),
        median: weightedMedian(cells),
        n: cells.reduce((s, c) => s + c.n, 0),
        inside: band[0] < radiusKm,
      };
    }).filter((r) => r.median !== null);
  }, [hexes, work, radiusKm]);

  const nearest = rows[0]?.median ?? null;
  const farthest = rows[rows.length - 1]?.median ?? null;
  const savings = nearest && farthest ? nearest - farthest : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rent vs. distance to work</CardTitle>
        <CardDescription>
          {work
            ? `Median ${bedroomLabel(bedrooms)} rent by straight-line distance from your pin.`
            : "How much does living closer cost? Drop a pin to find out."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!work ? (
          <div className="flex h-[220px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
            <BriefcaseBusiness className="size-6 text-muted-foreground" />
            <p className="max-w-[26ch] text-sm text-muted-foreground">
              Set a work location on the map to compare rent in distance bands around it.
            </p>
            <Button size="sm" variant="outline" onClick={onStartPlacing}>
              Set work location
            </Button>
          </div>
        ) : (
          <>
            <ChartContainer config={config} className="h-[220px] w-full">
              <BarChart data={rows} margin={{ top: 18, left: -8, right: 4 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="band" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickFormatter={usdCompact} tickLine={false} axisLine={false} fontSize={11} width={56} />
                <ChartTooltip
                  cursor={false}
                  content={
                    <ChartTooltipContent
                      formatter={(value, _name, item) => (
                        <div className="flex w-full justify-between gap-4">
                          <span className="text-muted-foreground">{item.payload.n.toLocaleString()} tenancies</span>
                          <span className="font-mono font-medium tabular-nums">{usd(Number(value))}</span>
                        </div>
                      )}
                    />
                  }
                />
                <Bar dataKey="median" radius={4} isAnimationActive={false}>
                  {rows.map((r) => (
                    <Cell key={r.band} fill={r.inside ? "var(--chart-1)" : "var(--chart-4)"} />
                  ))}
                  <LabelList
                    dataKey="median"
                    position="top"
                    fontSize={10}
                    className="fill-muted-foreground font-mono"
                    formatter={(v) => usdCompact(Number(v))}
                  />
                </Bar>
              </BarChart>
            </ChartContainer>
            <p className="mt-2 text-xs text-muted-foreground">
              {savings !== null && savings > 0 ? (
                <>
                  The closest band runs{" "}
                  <span className="font-mono text-foreground tabular-nums">{usd(savings)}</span> / month above the
                  farthest. Amber bars fall inside your {radiusKm.toFixed(1)} km radius.
                </>
              ) : (
                <>Amber bars fall inside your {radiusKm.toFixed(1)} km radius.</>
              )}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
