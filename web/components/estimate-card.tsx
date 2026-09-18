"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EstimateResult } from "@/components/estimate-result";
import { UnitForm } from "@/components/unit-form";
import type { BedroomStats, Model } from "@/lib/data";
import { monthLabel } from "@/lib/format";
import type { Estimate, Unit } from "@/lib/model";

type Props = {
  model: Model;
  unit: Unit;
  onChange: (patch: Partial<Unit>) => void;
  estimate: Estimate;
  hoodStats: BedroomStats | undefined;
  cityMedian: number | null;
  referenceMonth: string | null;
};

export function EstimateCard({
  model,
  unit,
  onChange,
  estimate,
  hoodStats,
  cityMedian,
  referenceMonth,
}: Props) {
  const neighborhoods = Object.keys(model.neighborhoods).sort();
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Rent estimate</CardTitle>
            <CardDescription>
              Describe the apartment; pick the neighborhood here or on the map.
            </CardDescription>
          </div>
          {referenceMonth ? (
            <Badge variant="outline" className="shrink-0 font-mono text-[11px]">
              {monthLabel(referenceMonth)} $
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="grid gap-5">
        <UnitForm unit={unit} neighborhoods={neighborhoods} onChange={onChange} />
        <Separator />
        <EstimateResult
          estimate={estimate}
          neighborhood={unit.neighborhood}
          bedrooms={unit.bedrooms}
          hoodStats={hoodStats}
          cityMedian={cityMedian}
        />
      </CardContent>
    </Card>
  );
}
