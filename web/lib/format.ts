const usdFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function usd(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? "—" : usdFormatter.format(value);
}

/** $4.2k style, for axis ticks and dense tables. */
export function usdCompact(value: number): string {
  return value >= 1000 ? `$${(value / 1000).toFixed(1)}k` : `$${Math.round(value)}`;
}

export function signedPct(value: number, digits = 0): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

export function integer(value: number): string {
  return value.toLocaleString("en-US");
}

export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
