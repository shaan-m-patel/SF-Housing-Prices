"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ZoriData } from "@/lib/data";
import { monthLabel, signedPct, usd, usdCompact } from "@/lib/format";
import { cn } from "@/lib/utils";

const CITY = "city";

const config = {
  city: { label: "San Francisco", color: "var(--chart-3)" },
  zip: { label: "ZIP", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function TrendCard({ zori }: { zori: ZoriData }) {
  const zips = Object.keys(zori.regions).filter((r) => r !== CITY).sort();
  const [zip, setZip] = useState(zips.includes("94110") ? "94110" : zips[0]);

  const rows = useMemo(() => {
    const byMonth = new Map<string, { month: string; city?: number; zip?: number }>();
    for (const [month, value] of zori.regions[CITY] ?? []) byMonth.set(month, { month, city: value });
    for (const [month, value] of zori.regions[zip] ?? []) {
      byMonth.set(month, { ...(byMonth.get(month) ?? { month }), zip: value });
    }
    return [...byMonth.values()].sort((a, b) => a.month.localeCompare(b.month));
  }, [zori, zip]);

  const yoy = useMemo(() => {
    const series = zori.regions[zip] ?? [];
    const latest = series[series.length - 1];
    const prior = series.find(([m]) => m === shiftYear(latest?.[0]));
    return latest && prior ? { latest: latest[1], pct: (latest[1] / prior[1] - 1) * 100 } : null;
  }, [zori, zip]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Asking-rent trend</CardTitle>
        <CardDescription>Zillow Observed Rent Index, all unit types, since 2022.</CardDescription>
        <CardAction>
          <Select items={zips.map((z) => ({ value: z, label: z }))} value={zip} onValueChange={(v) => v && setZip(v)}>
            <SelectTrigger size="sm" aria-label="ZIP code">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {zips.map((z) => (
                <SelectItem key={z} value={z}>
                  {z}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-baseline gap-3">
          <span className="font-mono text-2xl font-semibold tabular-nums">{yoy ? usd(yoy.latest) : "—"}</span>
          {yoy ? (
            <Badge
              variant="outline"
              className={cn("font-mono tabular-nums", yoy.pct > 0 ? "text-negative" : "text-positive")}
            >
              {signedPct(yoy.pct, 1)} YoY
            </Badge>
          ) : null}
          <span className="text-xs text-muted-foreground">
            {zip} · {monthLabel(zori.latest_month)}
          </span>
        </div>
        <ChartContainer config={config} className="h-[176px] w-full">
          <LineChart data={rows} margin={{ top: 4, left: -8, right: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              fontSize={11}
              ticks={rows.filter((r) => r.month.endsWith("-01")).map((r) => r.month)}
              tickFormatter={(m: string) => m.slice(0, 4)}
            />
            <YAxis
              domain={["dataMin - 100", "dataMax + 100"]}
              tickFormatter={usdCompact}
              tickLine={false}
              axisLine={false}
              fontSize={11}
              width={56}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(label) => monthLabel(String(label))}
                  formatter={(value, name) => (
                    <div className="flex w-full justify-between gap-4">
                      <span className="text-muted-foreground">{name === "zip" ? zip : "San Francisco"}</span>
                      <span className="font-mono font-medium tabular-nums">{usd(Number(value))}</span>
                    </div>
                  )}
                />
              }
            />
            <Line type="monotone" dataKey="city" stroke="var(--color-city)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="zip" stroke="var(--color-zip)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ChartContainer>
        <p className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 bg-chart-1" /> {zip}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 bg-chart-3" /> San Francisco
          </span>
        </p>
      </CardContent>
    </Card>
  );
}

function shiftYear(month: string | undefined): string | undefined {
  if (!month) return undefined;
  const [y, m] = month.split("-");
  return `${Number(y) - 1}-${m}`;
}
