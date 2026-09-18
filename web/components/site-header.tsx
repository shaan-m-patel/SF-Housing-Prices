import { Code2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Summary } from "@/lib/data";
import { integer } from "@/lib/format";

export const REPO_URL = "https://github.com/shaan-m-patel/SF-Housing-Prices";

export function SiteHeader({ summary }: { summary: Summary }) {
  const updated = new Date(summary.built_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
  return (
    <header className="border-b bg-background/70 backdrop-blur">
      <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 lg:px-6">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary font-mono text-sm font-bold text-primary-foreground">
            SF
          </span>
          <div>
            <h1 className="text-base leading-tight font-semibold tracking-tight">SF Rent Atlas</h1>
            <p className="text-xs text-muted-foreground">
              What should an apartment in San Francisco rent for?
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge variant="secondary" className="font-mono tabular-nums">
            {integer(summary.modelable)} tenancies
          </Badge>
          <Badge variant="secondary" className="font-mono tabular-nums">
            {summary.neighborhoods} neighborhoods
          </Badge>
          <Badge variant="secondary" className="font-mono tabular-nums">
            {summary.date_range[0].slice(0, 4)} – {summary.date_range[1].slice(0, 4)}
          </Badge>
          <Badge variant="outline" className="font-mono tabular-nums text-muted-foreground">
            updated {updated}
          </Badge>
        </div>
        <div className="ml-auto">
          <Button
            variant="outline"
            size="sm"
            render={<a href={REPO_URL} target="_blank" rel="noreferrer" />}
          >
            <Code2 data-icon="inline-start" /> Source on GitHub
          </Button>
        </div>
      </div>
    </header>
  );
}
