/**
 * SaaS Toggle — pure UI component.
 * Features: checked/unchecked, labels, sizes, disabled state.
 *
 * No store, no API — all data via props.
 */
import type { SaasToggleProps } from "./types";

export default function SaasToggle({
  checked = false,
  onChange,
  label,
  description,
  size = "md",
  disabled = false,
  loading = false,
}: SaasToggleProps) {
  const sizeStyles: Record<string, { width: string; height: string; knobSize: string }> = {
    sm: { width: "36px", height: "20px", knobSize: "16px" },
    md: { width: "44px", height: "24px", knobSize: "20px" },
    lg: { width: "52px", height: "28px", knobSize: "24px" },
  };

  const handleClick = () => {
    if (!disabled && !loading) {
      onChange?.(!checked);
    }
  };

  const currentSize = sizeStyles[size];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "var(--spacing-sm)",
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
      onClick={handleClick}
    >
      {/* Toggle switch */}
      <div
        style={{
          position: "relative",
          width: currentSize.width,
          height: currentSize.height,
          borderRadius: "var(--toggle-radius)",
          background: checked ? "var(--color-primary)" : "var(--color-border)",
          transition: "var(--transition-normal)",
          flexShrink: 0,
          marginTop: label || description ? "2px" : 0,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "2px",
            left: checked ? `calc(100% - ${currentSize.knobSize} - 2px)` : "2px",
            width: currentSize.knobSize,
            height: currentSize.knobSize,
            borderRadius: "50%",
            background: "#fff",
            boxShadow: "var(--toggle-knob-shadow)",
            transition: "var(--transition-normal)",
          }}
        />
        {loading && (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: "12px",
                height: "12px",
                border: "2px solid rgba(255,255,255,0.3)",
                borderTopColor: "#fff",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
          </div>
        )}
      </div>

      {/* Label and description */}
      {(label || description) && (
        <div style={{ flex: 1 }}>
          {label && (
            <div
              style={{
                fontSize: "var(--font-size-sm)",
                fontWeight: "var(--font-weight-medium)",
                color: disabled ? "var(--color-text-disabled)" : "var(--color-text-primary)",
                marginBottom: description ? "2px" : 0,
              }}
            >
              {label}
            </div>
          )}
          {description && (
            <div
              style={{
                fontSize: "var(--font-size-xs)",
                color: disabled ? "var(--color-text-disabled)" : "var(--color-text-secondary)",
              }}
            >
              {description}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
