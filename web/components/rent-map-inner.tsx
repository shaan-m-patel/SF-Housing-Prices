"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { setWorkerUrl } from "maplibre-gl";
import { BriefcaseBusiness } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Layer,
  Map as MapGL,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import type { Feature, FeatureCollection, MultiPolygon, Point, Polygon } from "geojson";
import { LayerToggle, Legend, WorkControl, type MapLayer } from "@/components/map-controls";
import type { BedroomStats, NeighborhoodCollection } from "@/lib/data";
import { bedroomLabel } from "@/lib/data";
import { colorDomain, fillColorExpression } from "@/lib/color";
import { usd } from "@/lib/format";
import { circlePolygon, type HexProps, type LatLng } from "@/lib/geo";

// Self-hosted copy of the worker (see scripts/copy-maplibre-worker.mjs); the bundled URL 404s.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const MAP_STYLE = "https://tiles.openfreemap.org/styles/dark";
// Frame the city with room for the overlay panels (top) and legend/controls (bottom).
const INITIAL_VIEW = {
  bounds: [-122.525, 37.703, -122.352, 37.835] as [number, number, number, number],
  fitBoundsOptions: { padding: { top: 72, bottom: 96, left: 32, right: 32 } },
};
const MAX_BOUNDS: [number, number, number, number] = [-122.75, 37.6, -122.15, 37.9];
const ACCENT = "#f2c14e";

export type RentMapProps = {
  neighborhoods: NeighborhoodCollection;
  statsByHood: Map<string, BedroomStats>;
  hexes: FeatureCollection<Polygon, HexProps>;
  bedrooms: number;
  layer: MapLayer;
  onLayerChange: (layer: MapLayer) => void;
  selected: string;
  onSelect: (name: string) => void;
  hovered: string | null;
  onHover: (name: string | null) => void;
  work: LatLng | null;
  onWork: (v: LatLng | null) => void;
  radiusKm: number;
  onRadius: (km: number) => void;
  placing: boolean;
  onPlacing: (v: boolean) => void;
  within: { hexes: number; median: number | null };
};

type HoodProps = { name: string; median: number | null; n: number; p25: number | null; p75: number | null };
type Hover = { lng: number; lat: number; title: string; lines: string[] };

export default function RentMapInner(props: RentMapProps) {
  const { neighborhoods, statsByHood, hexes, bedrooms, layer, selected, hovered, work, radiusKm, placing } = props;
  const [popup, setPopup] = useState<Hover | null>(null);

  const hoodFc = useMemo<FeatureCollection<Polygon | MultiPolygon, HoodProps>>(() => ({
    type: "FeatureCollection",
    features: neighborhoods.features.map((f) => {
      const s = statsByHood.get(f.properties.name);
      return {
        ...f,
        properties: {
          name: f.properties.name,
          median: s?.rent_median ?? null,
          n: s?.n ?? 0,
          p25: s?.rent_p25 ?? null,
          p75: s?.rent_p75 ?? null,
        },
      };
    }),
  }), [neighborhoods, statsByHood]);

  const labelFc = useMemo<FeatureCollection<Point, { name: string }>>(() => ({
    type: "FeatureCollection",
    features: neighborhoods.features.map((f) => ({
      type: "Feature",
      properties: { name: f.properties.name },
      geometry: { type: "Point", coordinates: [f.properties.label[1], f.properties.label[0]] },
    })),
  }), [neighborhoods]);

  const hoodDomain = useMemo(
    () => colorDomain(hoodFc.features.map((f) => f.properties.median ?? NaN)),
    [hoodFc],
  );
  const hexDomain = useMemo(
    () => colorDomain(hexes.features.map((f) => f.properties.median ?? NaN)),
    [hexes],
  );
  const ring = useMemo<Feature<Polygon> | null>(
    () => (work ? circlePolygon(work, radiusKm) : null),
    [work, radiusKm],
  );

  const showHexes = layer === "hexes";
  const interactive = showHexes ? ["hex-fill", "hood-fill"] : ["hood-fill"];

  function onMouseMove(e: MapLayerMouseEvent) {
    const hood = e.features?.find((f) => f.layer.id === "hood-fill");
    const hex = e.features?.find((f) => f.layer.id === "hex-fill");
    const hoodName = (hood?.properties as HoodProps | undefined)?.name ?? null;
    props.onHover(hoodName);
    if (showHexes && hex) {
      // MapLibre drops null-valued properties in transit, so treat null and undefined alike.
      const p = hex.properties as Partial<HexProps>;
      const distance = p.distanceKm != null ? ` · ${p.distanceKm.toFixed(1)} km from work` : "";
      setPopup({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        title: hoodName ?? "Hex cell",
        lines: [`${bedroomLabel(bedrooms)} median ${usd(p.median)}`, `${p.n ?? 0} tenancies${distance}`],
      });
    } else if (hood) {
      const p = hood.properties as Partial<HoodProps> & { name: string; n: number };
      setPopup({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        title: p.name,
        lines: p.median
          ? [
              `${bedroomLabel(bedrooms)} median ${usd(p.median)}`,
              `IQR ${usd(p.p25)} – ${usd(p.p75)} · ${p.n.toLocaleString()} tenancies`,
            ]
          : [`Too few ${bedroomLabel(bedrooms)} tenancies`],
      });
    } else {
      setPopup(null);
    }
  }

  function onClick(e: MapLayerMouseEvent) {
    if (placing) {
      props.onWork({ lat: e.lngLat.lat, lng: e.lngLat.lng });
      props.onPlacing(false);
      return;
    }
    const hood = e.features?.find((f) => f.layer.id === "hood-fill");
    if (hood) props.onSelect((hood.properties as HoodProps).name);
  }

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border bg-card">
      <MapGL
        initialViewState={INITIAL_VIEW}
        mapStyle={MAP_STYLE}
        maxBounds={MAX_BOUNDS}
        minZoom={10}
        interactiveLayerIds={interactive}
        cursor={placing ? "crosshair" : hovered ? "pointer" : "grab"}
        onMouseMove={onMouseMove}
        onMouseLeave={() => {
          props.onHover(null);
          setPopup(null);
        }}
        onClick={onClick}
        attributionControl={{ compact: true }}
        style={{ width: "100%", height: "100%" }}
      >
        <Source id="hexes" type="geojson" data={hexes}>
          <Layer
            id="hex-fill"
            type="fill"
            layout={{ visibility: showHexes ? "visible" : "none" }}
            paint={{
              "fill-color": fillColorExpression("median", hexDomain),
              "fill-opacity": ["case", ["get", "within"], 0.78, 0.1],
            }}
          />
          <Layer
            id="hex-line"
            type="line"
            layout={{ visibility: showHexes ? "visible" : "none" }}
            paint={{ "line-color": "#0b0b0d", "line-opacity": 0.35, "line-width": 0.6 }}
          />
        </Source>
        <Source id="hoods" type="geojson" data={hoodFc}>
          <Layer
            id="hood-fill"
            type="fill"
            paint={{
              "fill-color": fillColorExpression("median", hoodDomain),
              "fill-opacity": showHexes
                ? 0
                : ["case", [">", ["coalesce", ["get", "median"], 0], 0], 0.6, 0.08],
            }}
          />
          <Layer
            id="hood-line"
            type="line"
            paint={{ "line-color": "#ffffff", "line-opacity": showHexes ? 0.35 : 0.25, "line-width": 0.9 }}
          />
          <Layer
            id="hood-hover"
            type="line"
            filter={["==", ["get", "name"], hovered ?? ""]}
            paint={{ "line-color": "#ffffff", "line-width": 2 }}
          />
          <Layer
            id="hood-selected"
            type="line"
            filter={["==", ["get", "name"], selected]}
            paint={{ "line-color": ACCENT, "line-width": 2.5 }}
          />
        </Source>
        <Source id="hood-labels" type="geojson" data={labelFc}>
          <Layer
            id="hood-label"
            type="symbol"
            minzoom={11.5}
            layout={{
              "text-field": ["get", "name"],
              "text-size": 11,
              "text-font": ["Noto Sans Regular"],
              "text-max-width": 8,
              "text-padding": 6,
            }}
            paint={{
              "text-color": "rgba(255,255,255,0.92)",
              "text-halo-color": "rgba(0,0,0,0.75)",
              "text-halo-width": 1.2,
            }}
          />
        </Source>
        {ring ? (
          <Source id="radius" type="geojson" data={ring}>
            <Layer id="radius-fill" type="fill" paint={{ "fill-color": ACCENT, "fill-opacity": 0.06 }} />
            <Layer
              id="radius-line"
              type="line"
              paint={{ "line-color": ACCENT, "line-width": 1.5, "line-dasharray": [2, 2] }}
            />
          </Source>
        ) : null}
        {work ? (
          <Marker longitude={work.lng} latitude={work.lat} anchor="center">
            <span className="flex size-8 items-center justify-center rounded-full border-2 border-background bg-primary text-primary-foreground shadow-lg">
              <BriefcaseBusiness className="size-4" />
            </span>
          </Marker>
        ) : null}
        {popup && !placing ? (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            closeButton={false}
            closeOnClick={false}
            offset={14}
            maxWidth="260px"
          >
            <div className="px-3 py-2">
              <div className="text-sm font-medium">{popup.title}</div>
              {popup.lines.map((line) => (
                <div key={line} className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {line}
                </div>
              ))}
            </div>
          </Popup>
        ) : null}
        <NavigationControl position="bottom-right" showCompass={false} />
      </MapGL>

      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
        <div className="flex items-start justify-between gap-3">
          <LayerToggle value={layer} onChange={props.onLayerChange} />
          <WorkControl
            work={work}
            placing={placing}
            radiusKm={radiusKm}
            within={props.within}
            onPlacing={props.onPlacing}
            onWork={props.onWork}
            onRadius={props.onRadius}
          />
        </div>
        <div className="mb-8 flex items-end justify-between gap-3">
          <Legend
            domain={showHexes ? hexDomain : hoodDomain}
            label={`Median ${bedroomLabel(bedrooms)} rent · ${showHexes ? "H3 hex (~0.1 km²)" : "neighborhood"}`}
          />
        </div>
      </div>
    </div>
  );
}
