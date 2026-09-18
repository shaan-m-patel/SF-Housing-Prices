"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";

// MapLibre touches `window`, so the map only renders on the client.
export const RentMap = dynamic(() => import("@/components/rent-map-inner"), {
  ssr: false,
  loading: () => (
    <div className="relative h-full min-h-[520px] w-full overflow-hidden rounded-xl border bg-card">
      <Skeleton className="absolute inset-0 rounded-none" />
      <div className="absolute inset-x-3 top-3 flex justify-between">
        <Skeleton className="h-8 w-44" />
        <Skeleton className="h-9 w-60" />
      </div>
      <div className="absolute bottom-11 left-3">
        <Skeleton className="h-14 w-52" />
      </div>
      <p className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
        Loading map…
      </p>
    </div>
  ),
});
