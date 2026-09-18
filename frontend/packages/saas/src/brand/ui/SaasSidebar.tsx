/**
 * SaaS Sidebar — pure UI component.
 * Renders nav items, supports collapse, badge, nested menu.
 *
 * Note: uses onNavigate(path) instead of <NavLink> to stay pure.
 */
import type { SaasSidebarProps, SidebarNavItem } from "./types";

export default function SaasSidebar({
  items,
  collapsed = false,
  onToggleCollapse,
  brandName = "",
  brandSlogan = "",
  activePath,
  onItemClick,
  footer,
}: SaasSidebarProps) {
  const width = collapsed ? "var(--sidebar-collapsed-width)" : "var(--sidebar-width)";

  const renderItem = (item: SidebarNavItem, level = 0) => {
    const active = activePath === item.path;
    const hasChildren = item.children && item.children.length > 0;

    return (
      <div key={item.path}>
        <div
          onClick={() => onItemClick?.(item.path)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--sidebar-icon-gap)",
            padding: "var(--sidebar-item-padding)",
            paddingLeft: collapsed ? undefined : `${level * 16 + 20}px`,
            borderRadius: "var(--sidebar-item-radius)",
            fontSize: "var(--sidebar-item-font-size)",
            color: active ? "var(--color-text-sidebar-active)" : "var(--color-text-sidebar)",
            background: active ? "var(--color-bg-sidebar-active)" : "transparent",
            borderRight: active ? "var(--sidebar-active-border)" : "2px solid transparent",
            cursor: "pointer",
            transition: "var(--transition-fast)",
            justifyContent: collapsed ? "center" : "flex-start",
            whiteSpace: "nowrap",
            overflow: "hidden",
          }}
          onMouseEnter={(e) => {
            if (!active) e.currentTarget.style.background = "var(--color-bg-sidebar-hover)";
          }}
          onMouseLeave={(e) => {
            if (!active) e.currentTarget.style.background = "transparent";
          }}
        >
          {item.icon && <span style={{ fontSize: "var(--sidebar-icon-size)", flexShrink: 0 }}>{item.icon}</span>}
          {!collapsed && <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>}
          {!collapsed && item.badge && (
            <span style={{
              background: "var(--color-danger)",
              color: "#fff",
              fontSize: 10,
              padding: "1px 6px",
              borderRadius: "var(--radius-full)",
              fontWeight: "var(--font-weight-bold)",
            }}>
              {item.badge}
            </span>
          )}
        </div>
        {/* Nested items */}
        {!collapsed && hasChildren && (
          <div style={{ marginTop: "var(--sidebar-item-gap)" }}>
            {item.children!.map((child) => renderItem(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        bottom: 0,
        width,
        display: "flex",
        flexDirection: "column",
        zIndex: "var(--z-sidebar)",
        backgroundColor: "var(--color-bg-sidebar)",
        color: "var(--color-text-sidebar)",
        transition: "var(--transition-sidebar)",
      }}
    >
      {/* Brand */}
      <div
        style={{
          padding: collapsed ? "16px 8px" : "16px 20px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
        }}
      >
        {!collapsed && (
          <div>
            <h1 style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-bold)", color: "#fff", margin: 0 }}>
              {brandName}
            </h1>
            {brandSlogan && <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-sidebar-muted)", margin: "2px 0 0" }}>{brandSlogan}</p>}
          </div>
        )}
        {collapsed && <span style={{ fontSize: 20, color: "#fff" }}>{brandName.charAt(0)}</span>}
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--color-text-sidebar-muted)",
              cursor: "pointer",
              fontSize: 16,
              padding: 4,
            }}
            title={collapsed ? "展开" : "收起"}
          >
            {collapsed ? "▶" : "◀"}
          </button>
        )}
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, padding: "var(--px-spacing-sm) 8px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "var(--sidebar-item-gap)" }}>
        {items.map((item) => renderItem(item))}
      </nav>

      {/* Footer */}
      {footer && (
        <div style={{ padding: "12px 16px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          {footer}
        </div>
      )}
    </aside>
  );
}
