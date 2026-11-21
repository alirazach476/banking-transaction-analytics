import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { compact, specProblems } from "./Analysis.jsx";

const data = JSON.parse(readFileSync(new URL("../public/analysis.json", import.meta.url), "utf-8"));

describe("analysis.json", () => {
  it("has sections with unique chart ids", () => {
    expect(data.sections.length).toBeGreaterThanOrEqual(8);
    const ids = data.sections.flatMap((s) => s.charts.map((c) => c.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBeGreaterThanOrEqual(45);
  });
  it("every chart spec is valid (data present, series keys numeric)", () => {
    const bad = data.sections.flatMap((s) => s.charts.map((c) => [c.id, specProblems(c)]).filter(([, p]) => p.length));
    expect(bad).toEqual([]);
  });
  it("every chart names its source", () => {
    const missing = data.sections.flatMap((s) => s.charts).filter((c) => !c.source).map((c) => c.id);
    expect(missing).toEqual([]);
  });
});

describe("compact", () => {
  it("formats magnitudes", () => {
    expect(compact(1500000)).toBe("1.5m");
    expect(compact(2500000000)).toBe("2.5bn");
    expect(compact(12.345)).toBe("12.35");
  });
});
