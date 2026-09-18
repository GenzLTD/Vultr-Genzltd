/**
 * SaaS Input — pure UI component.
 * Supports prefix/suffix slots (for icons or units).
 */
import { useState } from "react";
import type { SaasInputProps } from "./types";

export default function SaasInput({
  value,
  onChange,
  placeholder = "",
  disabled = false,
  error = false,
  size = "md",
  label,
  helperText,
  type = "text",
  prefix,
  suffix,
  onKeyDown,
}: SaasInputProps) {
  const [focused, setFocused] = useState(false);

  const heights: Record<string, string> = {
    sm: "var(--input-height-sm)",
    md: "var(--input-height-md)",
    lg: "var(--input-height-lg)",
  };

  const wrapperStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "var(--radius-sm)",
    height: heights[size],
    padding: "0 var(--input-padding)",
    background: disabled ? "var(--input-bg-disabled)" : focused ? "var(--input-bg-focus)" : "var(--input-bg)",
    border: error
      ? "var(--input-border-error)"
      : focused
      ? "var(--input-border-focus)"
      : "var(--input-border)",
    borderRadius: "var(--input-radius)",
    boxShadow: focused && !error ? "var(--input-shadow-focus)" : "none",
    transition: "var(--transition-fast)",
    boxSizing: "border-box",
  };

  const inputStyle: React.CSSProperties = {
    flex: 1,
    border: "none",
    outline: "none",
    background: "transparent",
    color: disabled ? "var(--color-text-muted)" : "var(--color-text-primary)",
    fontSize: "var(--input-font-size)",
    fontFamily: "var(--font-family)",
    height: "100%",
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
      <div style={wrapperStyle} onFocusCapture={() => setFocused(true)} onBlurCapture={() => setFocused(false)}>
        {prefix && <span style={{ color: "var(--color-text-muted)", display: "flex", alignItems: "center" }}>{prefix}</span>}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          style={inputStyle}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
        {suffix && <span style={{ color: "var(--color-text-muted)", display: "flex", alignItems: "center" }}>{suffix}</span>}
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
