/**
 * Account data rights — export (GDPR Art.15/20, PIPL 第 45 条)
 * and self-service deletion (Art.17 / PIPL 第 47 条).
 *
 * Calls:
 *   GET    /v1/account/export
 *   DELETE /v1/account   body { confirm: "DELETE" }
 */
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";

const DELETE_WORD = "DELETE";

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function errorText(err: unknown, fallback: string): { message: string; orders: string[] } {
  if (err instanceof ApiError) {
    const orders = Array.isArray(err.body?.orders) ? err.body.orders.map(String) : [];
    return { message: String(err.body?.message || err.message || fallback), orders };
  }
  return { message: fallback, orders: [] };
}

export default function AccountDataSettings() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const logout = useSaasAuthStore((s) => s.logout);
  const api = useMemo(() => createSaasApiClient(), []);

  const [includeAudit, setIncludeAudit] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteMsg, setDeleteMsg] = useState<string | null>(null);
  const [blockedOrders, setBlockedOrders] = useState<string[]>([]);

  const handleExport = async () => {
    setExporting(true);
    setExportMsg(null);
    try {
      const payload = await api.get<unknown>(
        "/v1/account/export",
        includeAudit ? { include_audit: "1" } : undefined,
        { timeout: 120000 },
      );
      const stamp = new Date().toISOString().slice(0, 10);
      downloadJson(`account-export-${stamp}.json`, payload);
      setExportMsg(t("accountData.exportDone"));
    } catch (err) {
      setExportMsg(errorText(err, t("accountData.exportFailed")).message);
    } finally {
      setExporting(false);
    }
  };

  const handleDelete = async () => {
    if (confirmText.trim() !== DELETE_WORD) return;
    setDeleting(true);
    setDeleteMsg(null);
    setBlockedOrders([]);
    try {
      await api.delete("/v1/account", undefined, { body: { confirm: DELETE_WORD } });
      logout();
      navigate("/login", { replace: true });
    } catch (err) {
      const parsed = errorText(err, t("accountData.deleteFailed"));
      setDeleteMsg(parsed.message);
      setBlockedOrders(parsed.orders);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
        {t("accountData.title")}
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--color-text-muted)" }}>
        {t("accountData.subtitle")}{" "}
        <Link to="/settings/consent" style={{ color: "var(--color-primary)" }}>
          {t("nav.consent")}
        </Link>
      </p>

      <section
        className="rounded-lg p-4 mb-6"
        style={{
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-sm)",
          border: "1px solid #f0f0f0",
        }}
      >
        <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--color-text-primary)" }}>
          {t("accountData.exportTitle")}
        </h2>
        <p className="text-xs leading-relaxed mb-3" style={{ color: "var(--color-text-muted)" }}>
          {t("accountData.exportHint")}
        </p>
        <label className="flex items-center gap-2 text-xs mb-3" style={{ color: "var(--color-text-secondary)" }}>
          <input
            type="checkbox"
            checked={includeAudit}
            onChange={(e) => setIncludeAudit(e.target.checked)}
          />
          {t("accountData.includeAudit")}
        </label>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={exporting}
          className="text-sm px-4 py-2 rounded-lg font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {exporting ? t("accountData.exporting") : t("accountData.export")}
        </button>
        {exportMsg && (
          <p className="text-xs mt-3" style={{ color: "var(--color-text-secondary)" }}>
            {exportMsg}
          </p>
        )}
      </section>

      <section
        className="rounded-lg p-4"
        style={{
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-sm)",
          border: "1px solid #f0f0f0",
        }}
      >
        <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--color-danger, #c62828)" }}>
          {t("accountData.deleteTitle")}
        </h2>
        <p className="text-xs leading-relaxed mb-3" style={{ color: "var(--color-text-muted)" }}>
          {t("accountData.deleteHint")}
        </p>
        <label className="block text-xs mb-1" style={{ color: "var(--color-text-secondary)" }}>
          {t("accountData.confirmLabel")}
        </label>
        <input
          type="text"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          className="w-full max-w-xs text-sm px-3 py-2 rounded mb-3"
          style={{ border: "1px solid #e0e0e0" }}
          placeholder={DELETE_WORD}
        />
        <div>
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={deleting || confirmText.trim() !== DELETE_WORD}
            className="text-sm px-4 py-2 rounded-lg font-medium text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--color-danger, #c62828)" }}
          >
            {deleting ? t("accountData.deleting") : t("accountData.delete")}
          </button>
        </div>
        {deleteMsg && (
          <p className="text-xs mt-3" style={{ color: "var(--color-text-secondary)" }}>
            {deleteMsg}
          </p>
        )}
        {blockedOrders.length > 0 && (
          <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
            {t("accountData.paidOrders", { orders: blockedOrders.join(", ") })}
          </p>
        )}
      </section>
    </div>
  );
}
