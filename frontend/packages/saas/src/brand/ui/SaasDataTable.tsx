/**
 * SaaS DataTable — pure UI component.
 * Features: sorting, pagination, selection, compact mode, loading, empty.
 */
import type { SaasDataTableProps, DataTableColumn } from "./types";

export default function SaasDataTable<T extends Record<string, unknown>>({
  columns,
  data,
  rowKey = "id",
  loading = false,
  emptyText = "暂无数据",
  compact = false,
  selectable = false,
  selectedKeys = [],
  onRowSelect,
  onSort,
  pageSize,
  currentPage = 1,
  total = 0,
  onPageChange,
}: SaasDataTableProps<T>) {
  const cellPadding = compact ? "var(--table-cell-padding-compact)" : "var(--table-cell-padding)";
  const totalPages = pageSize ? Math.ceil(total / pageSize) : 1;

  const alignStyle = (align?: "left" | "center" | "right"): React.CSSProperties => ({
    textAlign: align || "left",
  });

  return (
    <div style={{
      background: "var(--table-bg)",
      borderRadius: "var(--table-radius)",
      border: "var(--table-border)",
      overflow: "hidden",
    }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          {/* Header */}
          <thead>
            <tr style={{ background: "var(--table-header-bg)" }}>
              {selectable && (
                <th style={{ padding: cellPadding, width: 40, ...alignStyle("center") }}>
                  <input
                    type="checkbox"
                    checked={selectedKeys.length === data.length && data.length > 0}
                    onChange={(e) => data.forEach((row) => onRowSelect?.(String(row[rowKey]), e.target.checked))}
                    style={{ cursor: "pointer" }}
                  />
                </th>
              )}
              {columns.map((col: DataTableColumn<T>) => (
                <th
                  key={col.key}
                  onClick={() => col.sortable && onSort?.(col.key, "asc")}
                  style={{
                    padding: cellPadding,
                    fontSize: "var(--table-header-font-size)",
                    fontWeight: "var(--table-header-font-weight)",
                    color: "var(--table-header-color)",
                    textTransform: "uppercase",
                    letterSpacing: "var(--table-header-letter-spacing)",
                    borderBottom: "var(--table-border-header)",
                    cursor: col.sortable ? "pointer" : "default",
                    width: col.width,
                    ...alignStyle(col.align),
                  }}
                >
                  {col.title}
                  {col.sortable && <span style={{ marginLeft: 4, opacity: 0.5 }}>⇅</span>}
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {loading && (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} style={{ padding: "40px", textAlign: "center" }}>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                    加载中...
                  </span>
                </td>
              </tr>
            )}

            {!loading && data.length === 0 && (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} style={{ padding: "40px", textAlign: "center" }}>
                  <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                    {emptyText}
                  </span>
                </td>
              </tr>
            )}

            {!loading && data.map((row, idx) => {
              const key = String(row[rowKey]);
              const selected = selectedKeys.includes(key);
              return (
                <tr
                  key={key || idx}
                  style={{
                    background: selected ? "var(--table-bg-selected)" : idx % 2 === 0 ? "var(--table-bg)" : "var(--table-bg-stripe)",
                    transition: "var(--transition-fast)",
                  }}
                  onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = "var(--table-bg-hover)"; }}
                  onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = idx % 2 === 0 ? "var(--table-bg)" : "var(--table-bg-stripe)"; }}
                >
                  {selectable && (
                    <td style={{ padding: cellPadding, ...alignStyle("center") }}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={(e) => onRowSelect?.(key, e.target.checked)}
                        style={{ cursor: "pointer" }}
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        padding: cellPadding,
                        fontSize: "var(--table-cell-font-size)",
                        color: "var(--table-cell-color)",
                        borderBottom: "1px solid var(--color-border-light)",
                        ...alignStyle(col.align),
                      }}
                    >
                      {col.render ? col.render(row) : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageSize && totalPages > 1 && (
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: "var(--radius-sm)",
          padding: "8px 16px",
          borderTop: "1px solid var(--color-border-light)",
        }}>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
            共 {total} 条，第 {currentPage}/{totalPages} 页
          </span>
          <button
            disabled={currentPage <= 1}
            onClick={() => onPageChange?.(currentPage - 1)}
            style={{
              padding: "4px 10px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-bg-card)",
              color: currentPage <= 1 ? "var(--color-text-muted)" : "var(--color-text-primary)",
              cursor: currentPage <= 1 ? "not-allowed" : "pointer",
              fontSize: "var(--font-size-xs)",
            }}
          >
            上一页
          </button>
          <button
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange?.(currentPage + 1)}
            style={{
              padding: "4px 10px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-bg-card)",
              color: currentPage >= totalPages ? "var(--color-text-muted)" : "var(--color-text-primary)",
              cursor: currentPage >= totalPages ? "not-allowed" : "pointer",
              fontSize: "var(--font-size-xs)",
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
