import { describe, expect, it } from "vitest";
import {
  isValidEmail,
  isPasswordStrong,
  isNotEmpty,
  isValidPhone,
  isValidUrl,
} from "./validation";

describe("validation", () => {
  it("isValidEmail accepts common formats", () => {
    expect(isValidEmail("user@example.com")).toBe(true);
    expect(isValidEmail("a.b+c@corp.co.uk")).toBe(true);
  });

  it("isValidEmail rejects invalid formats", () => {
    expect(isValidEmail("")).toBe(false);
    expect(isValidEmail("not-an-email")).toBe(false);
    expect(isValidEmail("@missing.local")).toBe(false);
  });

  it("isPasswordStrong requires 8+ chars", () => {
    expect(isPasswordStrong("1234567")).toBe(false);
    expect(isPasswordStrong("12345678")).toBe(true);
  });

  it("isNotEmpty trims whitespace", () => {
    expect(isNotEmpty("  hi  ")).toBe(true);
    expect(isNotEmpty("   ")).toBe(false);
    expect(isNotEmpty(null)).toBe(false);
  });

  it("isValidPhone matches mainland mobile", () => {
    expect(isValidPhone("13800138000")).toBe(true);
    expect(isValidPhone("23800138000")).toBe(false);
  });

  it("isValidUrl validates absolute URLs", () => {
    expect(isValidUrl("https://example.com/v1/health")).toBe(true);
    expect(isValidUrl("not-a-url")).toBe(false);
  });
});
