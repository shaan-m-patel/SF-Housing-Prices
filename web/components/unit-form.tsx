"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  BATHROOM_OPTIONS,
  BEDROOM_OPTIONS,
  BUILDING_OPTIONS,
  YEAR_BUILT_OPTIONS,
} from "@/lib/data";
import type { Unit } from "@/lib/model";

type Props = {
  unit: Unit;
  neighborhoods: string[];
  onChange: (patch: Partial<Unit>) => void;
};

const SQFT_MIN = 250;
const SQFT_MAX = 2500;

export function UnitForm({ unit, neighborhoods, onChange }: Props) {
  const hoodItems = neighborhoods.map((n) => ({ value: n, label: n }));
  return (
    <div className="grid gap-4">
      <Field label="Neighborhood">
        <Select
          items={hoodItems}
          value={unit.neighborhood}
          onValueChange={(v) => v && onChange({ neighborhood: v })}
        >
          <SelectTrigger className="w-full" aria-label="Neighborhood">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {hoodItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="Bedrooms">
        <ToggleGroup
          variant="outline"
          spacing={0}
          className="w-full *:flex-1"
          value={[String(unit.bedrooms)]}
          onValueChange={(v) => v.length && onChange({ bedrooms: Number(v[0]) })}
        >
          {BEDROOM_OPTIONS.map((o) => (
            <ToggleGroupItem key={o.value} value={String(o.value)} aria-label={o.label}>
              {o.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Field>

      <Field label="Bathrooms">
        <ToggleGroup
          variant="outline"
          spacing={0}
          className="w-full *:flex-1"
          value={[String(unit.bathrooms)]}
          onValueChange={(v) => v.length && onChange({ bathrooms: Number(v[0]) })}
        >
          {BATHROOM_OPTIONS.map((o) => (
            <ToggleGroupItem key={o.value} value={String(o.value)} aria-label={`${o.label} bath`}>
              {o.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Field>

      <Field
        label="Size"
        hint={
          unit.sqft ? `${unit.sqft.toLocaleString()} sq ft` : "not sure"
        }
      >
        <Slider
          min={SQFT_MIN}
          max={SQFT_MAX}
          step={25}
          value={[unit.sqft ?? 700]}
          onValueChange={(v) => onChange({ sqft: Array.isArray(v) ? v[0] : v })}
          aria-label="Square feet"
        />
        <div className="mt-1.5 flex justify-between font-mono text-[11px] text-muted-foreground">
          <span>{SQFT_MIN}</span>
          <span>{SQFT_MAX.toLocaleString()}+</span>
        </div>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Year built">
          <Select
            items={YEAR_BUILT_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            value={unit.yearBuilt}
            onValueChange={(v) => v && onChange({ yearBuilt: v })}
          >
            <SelectTrigger className="w-full" aria-label="Year built">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {YEAR_BUILT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Building">
          <Select
            items={BUILDING_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            value={unit.buildingUnits}
            onValueChange={(v) => v && onChange({ buildingUnits: v })}
          >
            <SelectTrigger className="w-full" aria-label="Building size">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BUILDING_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-baseline justify-between">
        <Label className="text-xs font-medium text-muted-foreground">{label}</Label>
        {hint ? <span className="font-mono text-xs text-foreground">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}
