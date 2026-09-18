import { REPO_URL } from "@/components/site-header";
import type { Summary } from "@/lib/data";
import { integer, monthLabel, usd } from "@/lib/format";

export function MethodNote({ summary }: { summary: Summary }) {
  const items = [
    {
      title: "Data",
      body: `${integer(summary.modelable)} tenancies from the SF Rent Board's Housing Inventory (2022 onward), geocoded to the block and grouped into ${summary.neighborhoods} analysis neighborhoods and ${integer(summary.hexes)} H3 hexes. Rents are Rent Board bands and in-place rents, adjusted to ${summary.reference_month ? monthLabel(summary.reference_month) : "current"} dollars with Zillow's ZORI.`,
    },
    {
      title: "Model",
      body: `A log-linear hedonic regression on ${integer(summary.model.n)} tenancies: a baseline per neighborhood plus bedroom, bathroom, size, building-age and building-size effects. R² ${summary.model.r2.toFixed(2)}; typical error ${usd(summary.model.holdout_mae)} (${Math.round(summary.model.holdout_mape * 100)}%) on held-out units. The range shows where 80% of comparable units land.`,
    },
    {
      title: "Caveats",
      body: `In-place rents run below fresh asking rents even after ZORI adjustment, so treat estimates as a floor for new leases. Amenity effects (laundry, parking, kitchen) will appear once the Craigslist collector has enough postings; ${summary.amenity_listings} so far. Distances are straight-line, not travel time.`,
    },
  ];
  return (
    <footer className="mt-8 border-t pt-6 text-sm">
      <div className="grid gap-6 md:grid-cols-3">
        {items.map((item) => (
          <div key={item.title}>
            <h2 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">{item.title}</h2>
            <p className="leading-relaxed text-muted-foreground">{item.body}</p>
          </div>
        ))}
      </div>
      <p className="mt-6 text-xs text-muted-foreground">
        Open source:{" "}
        <a href={REPO_URL} className="underline decoration-dotted underline-offset-2 hover:text-foreground">
          shaan-m-patel/SF-Housing-Prices
        </a>{" "}
        · Data: DataSF Rent Board, Zillow ZORI (non-commercial), OpenFreeMap tiles © OpenMapTiles & OpenStreetMap
        contributors.
      </p>
    </footer>
  );
}
