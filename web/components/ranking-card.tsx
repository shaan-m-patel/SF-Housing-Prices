"use client";

import { ArrowDownNarrowWide, ArrowUpNarrowWide } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { colorDomain, rentColor } from "@/lib/color";
import type { BedroomStats, NeighborhoodCollection } from "@/lib/data";
import { bedroomLabel } from "@/lib/data";
import { usd } from "@/lib/format";
import { haversineKm, type LatLng } from "@/lib/geo";
import { cn } from "@/lib/utils";

type Props = {
  statsByHood: Map<string, BedroomStats>;
  neighborhoods: NeighborhoodCollection;
  bedrooms: number;
  selected: string;
  hovered: string | null;
  work: LatLng | null;
  onSelect: (name: string) => void;
  onHover: (name: string | null) => void;
};

export function RankingCard({ statsByHood, neighborhoods, bedrooms, selected, hovered, work, onSelect, onHover }: Props) {
  const [ascending, setAscending] = useState(true);

  const rows = useMemo(() => {
    const labels = new Map(neighborhoods.features.map((f) => [f.properties.name, f.properties.label]));
    const list = [...statsByHood.values()].map((s) => {
      const label = labels.get(s.analysis_neighborhood);
      const distance = work && label ? haversineKm(work, { lat: label[0], lng: label[1] }) : null;
      return { ...s, distance };
    });
    return list.sort((a, b) => (ascending ? a.rent_median - b.rent_median : b.rent_median - a.rent_median));
  }, [statsByHood, neighborhoods, work, ascending]);

  const domain = useMemo(() => colorDomain(rows.map((r) => r.rent_median)), [rows]);
  const maxP75 = Math.max(...rows.map((r) => r.rent_p75), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Neighborhoods ranked</CardTitle>
        <CardDescription>
          Median {bedroomLabel(bedrooms)} rent with the interquartile range. Click a row to estimate there.
        </CardDescription>
        <CardAction>
          <Button size="sm" variant="ghost" onClick={() => setAscending((v) => !v)}>
            {ascending ? <ArrowUpNarrowWide data-icon="inline-start" /> : <ArrowDownNarrowWide data-icon="inline-start" />}
            {ascending ? "Cheapest first" : "Priciest first"}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2">
        <ScrollArea className="h-[268px] px-2">
          <ul className="grid gap-0.5" onMouseLeave={() => onHover(null)}>
            {rows.map((row, i) => {
              const active = row.analysis_neighborhood === selected;
              const hot = row.analysis_neighborhood === hovered;
              return (
                <li key={row.analysis_neighborhood}>
                  <button
                    type="button"
                    onClick={() => onSelect(row.analysis_neighborhood)}
                    onMouseEnter={() => onHover(row.analysis_neighborhood)}
                    className={cn(
                      "grid w-full grid-cols-[1.5rem_minmax(0,1fr)_5.5rem_auto] items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                      active ? "bg-primary/10 ring-1 ring-primary/50" : hot ? "bg-muted" : "hover:bg-muted/60",
                    )}
                  >
                    <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block truncate">{row.analysis_neighborhood}</span>
                      <span className="mt-1 block h-1 w-full rounded-full bg-muted">
                        <span
                          className="block h-full rounded-full"
                          style={{
                            marginLeft: `${(row.rent_p25 / maxP75) * 100}%`,
                            width: `${((row.rent_p75 - row.rent_p25) / maxP75) * 100}%`,
                            background: rentColor(row.rent_median, domain),
                          }}
                        />
                      </span>
                    </span>
                    <span className="text-right font-mono text-sm tabular-nums">{usd(row.rent_median)}</span>
                    <span className="w-14 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
                      {row.distance !== null ? `${row.distance.toFixed(1)} km` : `n=${row.n.toLocaleString()}`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
