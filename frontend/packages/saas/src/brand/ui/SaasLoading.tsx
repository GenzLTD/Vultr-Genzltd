/**
 * SaaS Loading + Skeleton - pure UI components.
 */
import type { SaasLoadingProps, SaasSkeletonProps } from "./types";

const SIZES: Record<string, number> = {
  sm: 16,
  md: 24,
  lg: 36,
};

export function SaasLoading({ size = "md", text, fullscreen = false }: SaasLoadingProps) {
  const px = SIZES[size];
  const borderWidth = Math.max(2, px / 10);

  const spinner = (
    <span
      style={{
        display: "inline-block",
        width: px,
        height: px,
        border: borderWidth + "px solid var(--color-border)",
        borderTopColor: "var(--color-primary)",
        borderRadius: "50%",
        animation: "xSpin 0.7s linear infinite",
      }}
    />
  );

  if (fullscreen) {
    return (
      <div
        style={{
          position: "fixed",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "var(--radius-md)",
          background: "var(--color-bg-page)",
          zIndex: "var(--z-modal)",
        }}
      >
        {spinner}
        {text && (
          <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{text}</span>
        )}
      </div>
    );
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--radius-sm)" }}>
      {spinner}
      {text && (
        <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{text}</span>
      )}
    </span>
  );
}

export function SaasSkeleton({ width = "100%", height = 20, rounded = false, count = 1 }: SaasSkeletonProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--radius-sm)" }}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            width: width,
            height: height,
            background:
              "linear-gradient(90deg, var(--color-bg-surface) 0%, var(--color-bg-hover) 50%, var(--color-bg-surface) 100%)",
            backgroundSize: "200% 100%",
            borderRadius: rounded ? "var(--radius-full)" : "var(--radius-sm)",
            animation: "shimmer 1.5s linear infinite",
          }}
        />
      ))}
    </div>
  );
}
