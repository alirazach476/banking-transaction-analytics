import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { specProblems, toOption } from "./lib/spec.js";
import { compact, deltaText, pct, usd } from "./lib/format.js";

const data = JSON.parse(readFileSync(new URL("../public/analysis.json", import.meta.url), "utf-8"));
const tokens = { text: "#fff", text2: "#ccc", muted: "#999", grid: "#333", colors: ["#1", "#2", "#3", "#4", "#5", "#6", "#7", "#8"] };

describe("analysis.json", () => {
  it("has sections with unique chart ids", () => {
    expect(data.sections.length).toBeGreaterThanOrEqual(8);
    const ids = data.sections.flatMap((s) => s.charts.map((c) => c.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBeGreaterThanOrEqual(45);
  });
  it("every chart spec is valid", () => {
    const bad = data.sections.flatMap((s) => s.charts.map((c) => [c.id, specProblems(c)]).filter(([, p]) => p.length));
    expect(bad).toEqual([]);
  });
  it("every chart names its source", () => {
    expect(data.sections.flatMap((s) => s.charts).filter((c) => !c.source).map((c) => c.id)).toEqual([]);
  });
  it("every non-table chart converts to an ECharts option with data for each series", () => {
    for (const c of data.sections.flatMap((s) => s.charts).filter((c) => c.type !== "table")) {
      const o = toOption(c, tokens);
      expect(o.series.length, c.id).toBeGreaterThan(0);
      for (const s of o.series) expect(s.data.length, c.id).toBe(c.data.length);
    }
  });
});

describe("format", () => {
  it("formats magnitudes", () => {
    expect(compact(1500000)).toBe("1.5M");
    expect(compact(2500000000)).toBe("2.5B");
    expect(usd(1234)).toBe("$1.2K");
    expect(pct(0.0512, 2)).toBe("5.12%");
    expect(deltaText(-3.456)).toBe("−3.46%");
    expect(deltaText(null)).toBe("n/a");
  });
});
