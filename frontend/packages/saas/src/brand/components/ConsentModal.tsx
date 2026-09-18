import type { ConsentScope } from "@looma/shared-core";
import { CONSENT_SCOPE_DESCRIPTIONS, CONSENT_SCOPE_LABELS } from "@looma/shared-core";

interface ConsentModalProps {
  scope: ConsentScope;
  onAccept: () => void;
  onDecline: () => void;
}

/**
 * PIPL 单独同意弹窗 — T-space B 端
 */
export default function ConsentModal({ scope, onAccept, onDecline }: ConsentModalProps) {
  const title = CONSENT_SCOPE_LABELS[scope];
  const description = CONSENT_SCOPE_DESCRIPTIONS[scope];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(0,0,0,0.55)",
        padding: "16px",
      }}
      onClick={onDecline}
    >
      <div
        style={{
          maxWidth: "420px",
          width: "100%",
          backgroundColor: "var(--color-bg-card, #fff)",
          borderRadius: "12px",
          padding: "24px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="consent-title" style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}>
          需要您的授权
        </h2>
        <p style={{ fontSize: "14px", color: "var(--color-text-muted, #666)", marginBottom: "12px" }}>
          <strong>{title}</strong>
        </p>
        <p style={{ fontSize: "13px", lineHeight: 1.6, marginBottom: "20px" }}>{description}</p>
        <p style={{ fontSize: "11px", color: "var(--color-text-muted, #999)", marginBottom: "16px" }}>
          依据《个人信息保护法》，该操作需单独同意。您可在设置中随时撤回授权。
        </p>
        <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onDecline}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "1px solid #ddd",
              background: "transparent",
              cursor: "pointer",
            }}
          >
            暂不授权
          </button>
          <button
            type="button"
            onClick={onAccept}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              background: "var(--color-primary, #2563eb)",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            同意并继续
          </button>
        </div>
      </div>
    </div>
  );
}
