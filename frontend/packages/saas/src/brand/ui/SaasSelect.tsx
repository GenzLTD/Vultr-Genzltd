/**
 * SaaS Select — pure UI component.
 * Styled native select for accessibility + simplicity.
 */
import { useState } from "react";
import type { SaasSelectProps } from "./types";

export default function SaasSelect({
  value,
  options,
  onChange,
  placeholder = "请选择",
  disabled = false,
  error = false,
  size = "md",
  label,
  helperText,
}: SaasSelectProps) {
  const [focused, setFocused] = useState(false);

  const heights: Record<string, string> = {
    sm: "var(--input-height-sm)",
    md: "var(--input-height-md)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--radius-xs)" }}>
      {label && (
        <label style={{
          color: "var(--label-color)",
          fontSize: "var(--label-font-size)",
          fontWeight: "var(--label-font-weight)",
        }}>
          {label}
        </label>
      )}
      <div
        style={{
          position: "relative",
          height: heights[size],
        }}
      >
        <select
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          disabled={disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: "100%",
            height: "100%",
            padding: "0 var(--input-padding)",
            paddingRight: 32,
            background: disabled ? "var(--input-bg-disabled)" : "var(--input-bg)",
            border: error
              ? "var(--input-border-error)"
              : focused
              ? "var(--input-border-focus)"
              : "var(--input-border)",
            borderRadius: "var(--input-radius)",
            color: disabled ? "var(--color-text-muted)" : value ? "var(--color-text-primary)" : "var(--color-text-muted)",
            fontSize: "var(--input-font-size)",
            fontFamily: "var(--font-family)",
            outline: "none",
            cursor: disabled ? "not-allowed" : "pointer",
            appearance: "none",
            WebkitAppearance: "none",
            MozAppearance: "none",
            boxSizing: "border-box",
          }}
        >
          {!value && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        {/* Chevron */}
        <span
          style={{
            position: "absolute",
            right: 12,
            top: "50%",
            transform: "translateY(-50%)",
            pointerEvents: "none",
            color: "var(--color-text-muted)",
            fontSize: 12,
          }}
        >
          ▼
        </span>
      </div>
      {helperText && (
        <span style={{
          fontSize: "var(--helper-font-size)",
          color: error ? "var(--helper-error)" : "var(--helper-color)",
        }}>
          {helperText}
        </span>
      )}
    </div>
  );
}
