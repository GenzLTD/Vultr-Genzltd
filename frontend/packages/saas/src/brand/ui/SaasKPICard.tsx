/**
 * SaaS KPICard — pure UI component.
 * Shows label, value, trend arrow, optional sparkline.
 */
import type { SaasKPICardProps } from "./types";

export default function SaasKPICard({
  label,
  value,
  unit,
  trend,
  trendValue,
  sparklineData,
  loading = false,
  error,
}: SaasKPICardProps) {
  const TREND_ICONS: Record<string, { icon: string; color: string }> = {
    up: { icon: "↑", color: "var(--kpi-trend-up)" },
    down: { icon: "↓", color: "var(--kpi-trend-down)" },
    flat: { icon: "→", color: "var(--color-text-muted)" },
  };

  // Simple inline SVG sparkline
  const renderSparkline = (data: number[]) => {
    if (data.length < 2) return null;
    const w = 80;
    const h = 24;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const pts = data.map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    });
    return (
      <svg width={w} height={h} style={{ display: "block" }}>
        <polyline
          points={pts.join(" ")}
          fill="none"
          stroke="var(--color-chart-1)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  };

  return (
    <div style={{
      background: "var(--card-bg)",
      border: "var(--card-border)",
      borderRadius: "var(--card-radius)",
      padding: "var(--kpi-card-padding)",
      boxShadow: "var(--shadow-sm)",
      display: "flex",
      flexDirection: "column",
      gap: "var(--kpi-card-gap)",
    }}>
      {/* Label */}
      <span style={{
        fontSize: "var(--kpi-label-font-size)",
        color: "var(--kpi-label-color)",
        fontWeight: "var(--font-weight-medium)",
      }}>
        {label}
      </span>

      {/* Loading */}
      {loading && (
        <div style={{
          height: "var(--kpi-value-font-size)",
          width: 80,
          background: "var(--color-bg-surface)",
          borderRadius: "var(--radius-sm)",
          animation: "shimmer 1.5s linear infinite",
        }} />
      )}

      {/* Error */}
      {error && !loading && (
        <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-danger)" }}>
          {error}
        </span>
      )}

      {/* Value + Trend */}
      {!loading && !error && (
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span style={{
              fontSize: "var(--kpi-value-font-size)",
              fontWeight: "var(--kpi-value-font-weight)",
              color: "var(--kpi-value-color)",
              lineHeight: 1,
            }}>
              {value}
            </span>
            {unit && (
              <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{unit}</span>
            )}
          </div>
          {sparklineData && renderSparkline(sparklineData)}
        </div>
      )}

      {/* Trend */}
      {trend && trendValue && !loading && !error && (
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: "var(--kpi-trend-font-size)", color: TREND_ICONS[trend].color, fontWeight: "var(--font-weight-semibold)" }}>
            {TREND_ICONS[trend].icon} {trendValue}
          </span>
          <span style={{ fontSize: "var(--kpi-trend-font-size)", color: "var(--color-text-muted)" }}>vs 上期</span>
        </div>
      )}
    </div>
  );
}
