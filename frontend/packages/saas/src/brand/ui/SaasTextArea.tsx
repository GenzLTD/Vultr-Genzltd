/**
 * SaaS TextArea — pure UI component.
 */
import { useState } from "react";
import type { SaasTextAreaProps } from "./types";

export default function SaasTextArea({
  value,
  onChange,
  placeholder = "",
  disabled = false,
  error = false,
  label,
  helperText,
  rows = 4,
  maxLength,
}: SaasTextAreaProps) {
  const [focused, setFocused] = useState(false);

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
      <textarea
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        maxLength={maxLength}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: "100%",
          padding: "10px 12px",
          background: disabled ? "var(--input-bg-disabled)" : focused ? "var(--input-bg-focus)" : "var(--input-bg)",
          border: error
            ? "var(--input-border-error)"
            : focused
            ? "var(--input-border-focus)"
            : "var(--input-border)",
          borderRadius: "var(--input-radius)",
          color: disabled ? "var(--color-text-muted)" : "var(--color-text-primary)",
          fontSize: "var(--input-font-size)",
          fontFamily: "var(--font-family)",
          outline: "none",
          transition: "var(--transition-fast)",
          resize: "vertical",
          boxSizing: "border-box",
          lineHeight: "var(--line-height-normal)",
        }}
      />
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
