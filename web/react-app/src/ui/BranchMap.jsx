import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useTheme } from "../lib/context.jsx";
import { int, pct, usd } from "../lib/format.js";

// City-centroid markers sized by transactions and coloured by failure rate. Basemap: OpenStreetMap raster tiles (dimmed in dark mode);
// if tiles cannot load (offline), markers still render on a plain background.
const style = (theme) => ({
  version: 8,
  sources: { base: { type: "raster", tileSize: 256, maxzoom: 18, attribution: "© OpenStreetMap contributors", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"] } },
  layers: [{ id: "bg", type: "background", paint: { "background-color": theme === "dark" ? "#0e1527" : "#e9eef7" } },
    { id: "base", type: "raster", source: "base", paint: theme === "dark" ? { "raster-opacity": 0.55, "raster-brightness-max": 0.35, "raster-saturation": -0.6, "raster-contrast": 0.1 } : { "raster-saturation": -0.4 } }],
});

export default function BranchMap({ markers, onSelect, height = 420 }) {
  const el = useRef(null);
  const map = useRef(null);
  const data = useRef(markers);
  const applied = useRef(null);
  const { theme } = useTheme();
  const [tilesOk, setTilesOk] = useState(true);
  data.current = markers;

  const addLayers = () => {
    const m = map.current;
    if (!m || m.getSource("cities")) return;
    const fc = { type: "FeatureCollection", features: data.current.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: c })) };
    m.addSource("cities", { type: "geojson", data: fc });
    m.addLayer({ id: "cities", type: "circle", source: "cities", paint: {
      "circle-radius": ["interpolate", ["linear"], ["sqrt", ["get", "transactions"]], 20, 7, 90, 22],
      "circle-color": ["step", ["get", "failure_rate"], "#2dd4bf", 0.05, "#fbbf24", 0.058, "#f87171"],
      "circle-opacity": 0.78, "circle-stroke-width": 1.5, "circle-stroke-color": theme === "dark" ? "#0a0f1e" : "#ffffff" } });
  };

  useEffect(() => {
    const m = new maplibregl.Map({ container: el.current, style: style(theme), center: [-96, 38.5], zoom: 3.2, attributionControl: { compact: true } });
    map.current = m;
    applied.current = theme;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("style.load", addLayers);
    m.on("error", (e) => { if (e?.error?.status || /tile|Failed to fetch/i.test(String(e?.error?.message))) setTilesOk(false); });
    m.on("click", "cities", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup({ closeButton: false, offset: 12 }).setLngLat(e.lngLat)
        .setHTML(`<div style="font:12px Inter,sans-serif;color:#0f172a"><b>${p.city}</b><br/>${p.branches} branch(es) · ${int(+p.transactions)} transactions<br/>${usd(+p.value)} completed · failure ${pct(+p.failure_rate, 2)}</div>`).addTo(m);
      onSelect && onSelect(p.city);
    });
    m.on("mouseenter", "cities", () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", "cities", () => (m.getCanvas().style.cursor = ""));
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { // theme change: swap basemap, then layers are re-added on style.load
    const m = map.current;
    if (!m) return;
    if (applied.current === theme) return; // initial style already uses this theme
    applied.current = theme;
    m.setStyle(style(theme));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  useEffect(() => { // new data
    const m = map.current;
    if (!m) return;
    const apply = () => {
      const src = m.getSource("cities");
      const fc = { type: "FeatureCollection", features: markers.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: c })) };
      if (src) src.setData(fc);
      if (markers.length) {
        const b = new maplibregl.LngLatBounds();
        markers.forEach((c) => b.extend([c.lon, c.lat]));
        m.fitBounds(b, { padding: 50, maxZoom: 5.5, duration: 0 });
      }
    };
    if (m.isStyleLoaded()) apply(); else m.once("style.load", apply);
  }, [markers]);

  return (
    <div style={{ position: "relative" }}>
      <div ref={el} style={{ height, borderRadius: 10, overflow: "hidden" }} role="img" aria-label="Map of branch cities" data-testid="branch-map" />
      <div className="legend-row" style={{ position: "absolute", left: 10, bottom: 10, background: "var(--surface)", padding: "6px 10px", borderRadius: 8, border: "1px solid var(--border)" }}>
        <span><i style={{ background: "#2dd4bf" }} />failure &lt; 5%</span><span><i style={{ background: "#fbbf24" }} />5-5.8%</span><span><i style={{ background: "#f87171" }} />&gt; 5.8%</span><span style={{ color: "var(--muted)" }}>size = transactions</span>
      </div>
      {!tilesOk && <div className="notice warn" style={{ position: "absolute", top: 10, left: 10, margin: 0 }}>Basemap tiles could not load (offline?). Markers are still positioned correctly.</div>}
    </div>
  );
}
