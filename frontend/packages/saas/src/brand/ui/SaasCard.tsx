/**
 * SaaS Card — pure UI component.
 */
import type { SaasCardProps } from "./types";

export default function SaasCard({
  padding = "md",
  hoverable = false,
  onClick,
  children,
  className = "",
}: SaasCardProps) {
  const paddings: Record<string, string> = {
    sm: "var(--card-padding-sm)",
    md: "var(--card-padding)",
    lg: "var(--card-padding-lg)",
  };

  return (
    <div
      className={className}
      style={{
        background: "var(--card-bg)",
        border: "var(--card-border)",
        borderRadius: "var(--card-radius)",
        padding: paddings[padding],
        boxShadow: "var(--card-shadow)",
        transition: "var(--transition-normal)",
        cursor: onClick ? "pointer" : "default",
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (hoverable || onClick) {
          e.currentTarget.style.boxShadow = "var(--card-shadow-hover)";
          e.currentTarget.style.borderColor = "var(--color-border)";
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "var(--card-shadow)";
        e.currentTarget.style.borderColor = "var(--color-border-light)";
      }}
    >
      {children}
    </div>
  );
}
