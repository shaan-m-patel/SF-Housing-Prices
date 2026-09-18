"use client";

import { BriefcaseBusiness, Crosshair, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { RENT_GRADIENT_CSS, type Domain } from "@/lib/color";
import { usd, usdCompact } from "@/lib/format";
import { HUBS, type LatLng } from "@/lib/geo";

export type MapLayer = "neighborhoods" | "hexes";

const panel =
  "pointer-events-auto rounded-lg border bg-popover/90 text-popover-foreground shadow-lg backdrop-blur";

export function LayerToggle({ value, onChange }: { value: MapLayer; onChange: (v: MapLayer) => void }) {
  return (
    <ToggleGroup
      size="sm"
      spacing={0}
      className={panel}
      value={[value]}
      onValueChange={(v) => v.length && onChange(v[0] as MapLayer)}
    >
      <ToggleGroupItem value="neighborhoods">Neighborhoods</ToggleGroupItem>
      <ToggleGroupItem value="hexes">Hex grid</ToggleGroupItem>
    </ToggleGroup>
  );
}

export function Legend({ domain, label }: { domain: Domain; label: string }) {
  return (
    <div className={`${panel} px-3 py-2`}>
      <div className="mb-1.5 text-[11px] text-muted-foreground">{label}</div>
      <div className="h-2 w-44 rounded-full" style={{ background: RENT_GRADIENT_CSS }} />
      <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground tabular-nums">
        <span>≤ {usdCompact(domain[0])}</span>
        <span>{usdCompact((domain[0] + domain[1]) / 2)}</span>
        <span>≥ {usdCompact(domain[1])}</span>
      </div>
    </div>
  );
}

type WorkProps = {
  work: LatLng | null;
  placing: boolean;
  radiusKm: number;
  within: { hexes: number; median: number | null };
  onPlacing: (v: boolean) => void;
  onWork: (v: LatLng | null) => void;
  onRadius: (km: number) => void;
};

export function WorkControl({ work, placing, radiusKm, within, onPlacing, onWork, onRadius }: WorkProps) {
  const hubItems = HUBS.map((h) => ({ value: h.name, label: h.name }));
  if (!work) {
    return (
      <div className={`${panel} grid w-60 gap-2 p-2.5`}>
        {placing ? (
          <div className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-1.5 text-primary">
              <Crosshair className="size-4" /> Click the map
            </span>
            <Button size="xs" variant="ghost" onClick={() => onPlacing(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button size="sm" className="w-full justify-start" onClick={() => onPlacing(true)}>
            <BriefcaseBusiness data-icon="inline-start" /> Set work location
          </Button>
        )}
        <Select
          items={hubItems}
          value={null}
          onValueChange={(v) => {
            const hub = HUBS.find((h) => h.name === v);
            if (hub) onWork({ lat: hub.lat, lng: hub.lng });
          }}
        >
          <SelectTrigger size="sm" className="w-full" aria-label="Pick a common work hub">
            <SelectValue placeholder="…or pick a hub" />
          </SelectTrigger>
          <SelectContent>
            {hubItems.map((h) => (
              <SelectItem key={h.value} value={h.value}>
                {h.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  }
  return (
    <div className={`${panel} grid w-64 gap-2.5 p-3`}>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          <BriefcaseBusiness className="size-4 text-primary" /> Work location
        </span>
        <Button size="icon-xs" variant="ghost" aria-label="Clear work location" onClick={() => onWork(null)}>
          <X />
        </Button>
      </div>
      <div>
        <div className="mb-1.5 flex items-baseline justify-between text-xs text-muted-foreground">
          <span>Radius</span>
          <span className="font-mono text-foreground tabular-nums">{radiusKm.toFixed(1)} km</span>
        </div>
        <Slider
          min={0.5}
          max={10}
          step={0.5}
          value={[radiusKm]}
          onValueChange={(v) => onRadius(Array.isArray(v) ? v[0] : v)}
          aria-label="Commute radius in kilometers"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        <span className="font-mono text-foreground tabular-nums">{within.hexes}</span> hexes inside ·
        median <span className="font-mono text-foreground tabular-nums">{usd(within.median)}</span>
      </p>
      <Button size="xs" variant="outline" onClick={() => onPlacing(true)}>
        <Crosshair data-icon="inline-start" /> Move pin
      </Button>
    </div>
  );
}
