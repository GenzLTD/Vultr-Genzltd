import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { clamp, formatPercent, truncate } from "./format";

describe("format utilities", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("truncate adds suffix when text exceeds max length", () => {
    expect(truncate("hello world", 8)).toBe("hello...");
    expect(truncate("short", 10)).toBe("short");
  });

  it("formatPercent multiplies by 100", () => {
    expect(formatPercent(0.9)).toBe("90.0%");
    expect(formatPercent(0.905, 2)).toBe("90.50%");
  });

  it("clamp bounds numeric values", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(99, 0, 10)).toBe(10);
  });
});
