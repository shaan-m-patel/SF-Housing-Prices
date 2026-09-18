"use client";

import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { BedroomStats } from "@/lib/data";
import { bedroomLabel } from "@/lib/data";
import { signedPct, usd } from "@/lib/format";
import { effectPct, type Estimate } from "@/lib/model";
import { cn } from "@/lib/utils";

type Props = {
  estimate: Estimate;
  neighborhood: string;
  bedrooms: number;
  hoodStats: BedroomStats | undefined;
  cityMedian: number | null;
};

export function EstimateResult({ estimate, neighborhood, bedrooms, hoodStats, cityMedian }: Props) {
  const { rent, band, base, terms } = estimate;
  const vsHood = hoodStats ? (rent / hoodStats.rent_median - 1) * 100 : null;
  const vsCity = cityMedian ? (rent / cityMedian - 1) * 100 : null;
  const maxAbs = Math.max(30, ...terms.map((t) => Math.abs(effectPct(t.value))));

  return (
    <div className="grid gap-5">
      <div>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[2.6rem] leading-none font-semibold tracking-tight tabular-nums">
            {usd(rent)}
          </span>
          <span className="text-sm text-muted-foreground">/ month</span>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Typical range{" "}
          <span className="font-mono text-foreground tabular-nums">
            {usd(band.p25)} – {usd(band.p75)}
          </span>
        </p>
      </div>

      <RangeBar rent={rent} band={band} marker={hoodStats?.rent_median ?? null} />

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <Comparison
          label={`${neighborhood} · ${bedroomLabel(bedrooms)} median`}
          value={hoodStats ? usd(hoodStats.rent_median) : "—"}
          delta={vsHood}
          note={hoodStats ? `${hoodStats.n.toLocaleString()} tenancies` : "too few tenancies"}
        />
        <Comparison
          label={`Citywide · ${bedroomLabel(bedrooms)} median`}
          value={usd(cityMedian)}
          delta={vsCity}
          note="all neighborhoods"
        />
      </dl>

      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            What drives it
          </h3>
          <span className="text-xs text-muted-foreground">
            {neighborhood} baseline{" "}
            <span className="font-mono text-foreground tabular-nums">{usd(base)}</span>
          </span>
        </div>
        <ul className="grid gap-1.5">
          {terms.map((term) => {
            const pct = effectPct(term.value);
            const width = Math.min(100, (Math.abs(pct) / maxAbs) * 100);
            return (
              <li key={term.key} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
                <div className="min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate">{term.label}</span>
                    <span
                      className={cn(
                        "font-mono text-xs tabular-nums",
                        pct > 0.5 ? "text-primary" : pct < -0.5 ? "text-chart-2" : "text-muted-foreground",
                      )}
                    >
                      {Math.abs(pct) < 0.5 ? "baseline" : signedPct(pct)}
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        pct > 0.5 ? "bg-primary" : pct < -0.5 ? "bg-chart-2" : "bg-transparent",
                      )}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <button
                        type="button"
                        aria-label={`Why ${term.label}`}
                        className="text-muted-foreground/70 hover:text-foreground"
                      />
                    }
                  >
                    <Info className="size-3.5" />
                  </TooltipTrigger>
                  <TooltipContent side="left">{term.detail}</TooltipContent>
                </Tooltip>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function RangeBar({
  rent,
  band,
  marker,
}: {
  rent: number;
  band: Estimate["band"];
  marker: number | null;
}) {
  const lo = Math.min(band.p10, marker ?? band.p10) * 0.97;
  const hi = Math.max(band.p90, marker ?? band.p90) * 1.03;
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const span = (a: number, b: number) => ({ left: pos(a), width: `${((b - a) / (hi - lo)) * 100}%` });
  return (
    <div>
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-muted" />
        <div className="absolute top-3 h-2 rounded-full bg-primary/30" style={span(band.p10, band.p90)} />
        <div className="absolute top-3 h-2 rounded-full bg-primary/80" style={span(band.p25, band.p75)} />
        {marker !== null ? (
          <Tooltip>
            <TooltipTrigger
              render={
                <span
                  className="absolute top-1.5 h-5 w-0.5 -translate-x-1/2 rounded bg-foreground/70"
                  style={{ left: pos(marker) }}
                />
              }
            />
            <TooltipContent>Neighborhood median {usd(marker)}</TooltipContent>
          </Tooltip>
        ) : null}
        <div
          className="absolute top-0.5 size-7 -translate-x-1/2 rounded-full border-[3px] border-background bg-primary shadow-[0_0_0_1px_var(--primary)]"
          style={{ left: pos(rent) }}
          aria-hidden
        />
      </div>
      <div className="flex justify-between font-mono text-[11px] text-muted-foreground tabular-nums">
        <span>{usd(band.p10)}</span>
        <span className="text-foreground/70">80% of similar units fall in this range</span>
        <span>{usd(band.p90)}</span>
      </div>
    </div>
  );
}

function Comparison({
  label,
  value,
  delta,
  note,
}: {
  label: string;
  value: string;
  delta: number | null;
  note: string;
}) {
  return (
    <div className="rounded-lg border bg-background/40 p-3">
      <dt className="truncate text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-base font-medium tabular-nums">{value}</span>
        {delta !== null ? (
          <span
            className={cn(
              "font-mono text-xs tabular-nums",
              delta > 0 ? "text-negative" : delta < 0 ? "text-positive" : "text-muted-foreground",
            )}
          >
            {signedPct(delta)}
          </span>
        ) : null}
      </dd>
      <dd className="text-[11px] text-muted-foreground">{note}</dd>
    </div>
  );
}
