/**
 * SaaS Button — pure UI component.
 * Variants: primary / secondary / outline / danger / ghost
 * Sizes: sm / md / lg
 */
import type { SaasButtonProps } from "./types";

export default function SaasButton({
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  fullWidth = false,
  leftIcon,
  rightIcon,
  children,
  onClick,
  type = "button",
}: SaasButtonProps) {
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "var(--btn-gap)",
    fontWeight: "var(--btn-font-weight)",
    borderRadius: "var(--btn-radius)",
    border: "none",
    cursor: disabled || loading ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    transition: "var(--transition-fast)",
    fontFamily: "var(--font-family)",
    width: fullWidth ? "100%" : "auto",
    pointerEvents: disabled || loading ? "none" : "auto",
    boxShadow: "var(--btn-shadow)",
  };

  const sizes: Record<string, React.CSSProperties> = {
    sm: { height: "var(--btn-height-sm)", padding: "var(--btn-padding-sm)", fontSize: "var(--btn-font-sm)" },
    md: { height: "var(--btn-height-md)", padding: "var(--btn-padding-md)", fontSize: "var(--btn-font-md)" },
    lg: { height: "var(--btn-height-lg)", padding: "var(--btn-padding-lg)", fontSize: "var(--btn-font-lg)" },
  };

  const variants: Record<string, React.CSSProperties> = {
    primary: { background: "var(--btn-bg-primary)", color: "var(--btn-text-primary)" },
    secondary: { background: "var(--btn-bg-secondary)", color: "var(--btn-text-secondary)", border: "1px solid var(--color-border)" },
    outline: { background: "var(--btn-bg-outline)", color: "var(--btn-text-outline)", border: "1px solid var(--color-border)" },
    danger: { background: "var(--btn-bg-danger)", color: "#fff" },
    ghost: { background: "transparent", color: "var(--color-text-secondary)", border: "none", boxShadow: "none" },
  };

  const hoverBg: Record<string, string> = {
    primary: "var(--btn-bg-primary-hover)",
    secondary: "var(--btn-bg-secondary-hover)",
    outline: "var(--btn-bg-outline-hover)",
    danger: "var(--btn-bg-danger-hover)",
    ghost: "var(--color-bg-hover)",
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{ ...base, ...sizes[size], ...variants[variant] }}
      onMouseEnter={(e) => {
        if (disabled || loading) return;
        e.currentTarget.style.background = hoverBg[variant];
        if (variant === "outline") e.currentTarget.style.borderColor = "var(--color-primary)";
        if (variant !== "ghost") e.currentTarget.style.boxShadow = "var(--btn-shadow-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = variants[variant].background as string;
        if (variant === "outline") e.currentTarget.style.borderColor = "var(--color-border)";
        e.currentTarget.style.boxShadow = variant === "ghost" ? "none" : "var(--btn-shadow)";
      }}
      onFocus={(e) => { e.currentTarget.style.boxShadow = "var(--btn-shadow-focus)"; }}
      onBlur={(e) => { e.currentTarget.style.boxShadow = variant === "ghost" ? "none" : "var(--btn-shadow)"; }}
    >
      {loading && (
        <span style={{
          display: "inline-block",
          width: 14,
          height: 14,
          border: "2px solid currentColor",
          borderTopColor: "transparent",
          borderRadius: "50%",
          animation: "xSpin 0.8s linear infinite",
        }} />
      )}
      {!loading && leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}
