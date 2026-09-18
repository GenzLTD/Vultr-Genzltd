/**
 * SaaS ProgressBar — pure UI component.
 * Features: determinate/indeterminate, color variants, label, size variants.
 *
 * No store, no API — all data via props.
 */
import type { SaasProgressBarProps } from "./types";

export default function SaasProgressBar({
  value = 0,
  max = 100,
  variant = "primary",
  size = "md",
  showLabel = false,
  labelPosition = "inside",
  labelFormat,
  indeterminate = false,
}: SaasProgressBarProps) {
  const percentage = Math.min(Math.max(value, 0), max);
  const progressPercent = (percentage / max) * 100;

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { height: "var(--progress-height-sm)" },
    md: { height: "var(--progress-height-md)" },
    lg: { height: "var(--progress-height-lg)" },
  };

  const variantColors: Record<string, { bg: string; bar: string }> = {
    primary: { bg: "var(--color-bg-surface)", bar: "var(--color-primary)" },
    success: { bg: "var(--color-success-light)", bar: "var(--color-success)" },
    warning: { bg: "var(--color-warning-light)", bar: "var(--color-warning)" },
    danger: { bg: "var(--color-danger-light)", bar: "var(--color-danger)" },
    info: { bg: "var(--color-info-light)", bar: "var(--color-info)" },
  };

  const defaultLabel = labelFormat ? labelFormat(percentage, max) : `${Math.round(progressPercent)}%`;

  return (
    <div style={{ width: "100%" }}>
      {(showLabel && labelPosition === "outside-top") && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: "var(--spacing-xs)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          <span>Progress</span>
          <span>{defaultLabel}</span>
        </div>
      )}

      <div
        style={{
          position: "relative",
          background: variantColors[variant].bg,
          borderRadius: "var(--progress-radius)",
          overflow: "hidden",
          ...sizeStyles[size],
        }}
      >
        {indeterminate ? (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              background: `linear-gradient(
                90deg,
                transparent 0%,
                ${variantColors[variant].bar} 50%,
                transparent 100%
              )`,
              backgroundSize: "200% 100%",
              animation: "indeterminate 1.5s ease-in-out infinite",
              borderRadius: "var(--progress-radius)",
            }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: `${progressPercent}%`,
              height: "100%",
              background: variantColors[variant].bar,
              borderRadius: "var(--progress-radius)",
              transition: "width 0.3s ease-out",
            }}
          />
        )}

        {(showLabel && labelPosition === "inside") && (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "var(--font-size-sm)",
              fontWeight: "var(--font-weight-medium)",
              color: progressPercent > 50 ? "#fff" : "var(--color-text-primary)",
              textShadow: progressPercent > 50 ? "0 1px 2px rgba(0,0,0,0.2)" : "none",
            }}
          >
            {defaultLabel}
          </div>
        )}
      </div>

      {(showLabel && labelPosition === "outside-bottom") && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: "var(--spacing-xs)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-secondary)",
          }}
        >
          <span>Progress</span>
          <span>{defaultLabel}</span>
        </div>
      )}

      <style>{`
        @keyframes indeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
