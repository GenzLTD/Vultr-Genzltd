/**
 * SaaS Modal — pure UI component.
 * Features: overlay, backdrop click close, size variants, centered.
 *
 * No store, no API — all data via props.
 */
import type { SaasModalProps } from "./types";

export default function SaasModal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  showClose = true,
  overlayClickClose = true,
  footer,
}: SaasModalProps) {
  if (!isOpen) return null;

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { maxWidth: "400px", padding: "var(--modal-padding-sm)" },
    md: { maxWidth: "600px", padding: "var(--modal-padding)" },
    lg: { maxWidth: "800px", padding: "var(--modal-padding-lg)" },
    xl: { maxWidth: "1000px", padding: "var(--modal-padding-lg)" },
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: "var(--z-modal)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--spacing-md)",
      }}
    >
      {/* Overlay */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "var(--color-bg-overlay)",
          animation: "fadeIn 150ms ease-out",
        }}
        onClick={overlayClickClose ? onClose : undefined}
      />

      {/* Modal content */}
      <div
        style={{
          position: "relative",
          background: "var(--color-bg-card)",
          borderRadius: "var(--modal-radius)",
          border: "var(--modal-border)",
          boxShadow: "var(--modal-shadow)",
          width: "100%",
          maxHeight: "calc(100vh - 80px)",
          display: "flex",
          flexDirection: "column",
          animation: "slideUp 200ms ease-out",
          ...sizeStyles[size],
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        {(title || showClose) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              paddingBottom: "var(--spacing-md)",
              marginBottom: "var(--spacing-md)",
              borderBottom: footer ? "1px solid var(--color-border-light)" : "none",
            }}
          >
            {title && (
              <h2
                style={{
                  margin: 0,
                  fontSize: "var(--font-size-lg)",
                  fontWeight: "var(--font-weight-semibold)",
                  color: "var(--color-text-primary)",
                }}
              >
                {title}
              </h2>
            )}
            {showClose && (
              <button
                onClick={onClose}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--color-text-muted)",
                  cursor: "pointer",
                  padding: "var(--spacing-xs)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "1.5rem",
                  lineHeight: 1,
                  transition: "var(--transition-fast)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-muted)")}
              >
                ×
              </button>
            )}
          </div>
        )}

        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            maxHeight: footer ? "calc(100vh - 240px)" : "calc(100vh - 160px)",
          }}
        >
          {children}
        </div>

        {/* Footer (if provided) */}
        {footer && (
          <div
            style={{
              marginTop: "var(--spacing-lg)",
              paddingTop: "var(--spacing-md)",
              borderTop: "1px solid var(--color-border-light)",
              display: "flex",
              gap: "var(--spacing-sm)",
              justifyContent: "flex-end",
            }}
          >
            {footer}
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
