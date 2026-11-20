import { describe, expect, it } from "vitest";

// api.js reads location at import time; provide a minimal global for the node test environment.
globalThis.location = { search: "" };
const { pct } = await import("./api.js");

describe("pct", () => {
  it("formats rates as percentages with two decimals", () => {
    expect(pct(0.95068)).toBe("95.07%");
    expect(pct(0)).toBe("0.00%");
  });
});
