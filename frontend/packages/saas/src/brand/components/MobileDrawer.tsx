/**
 * MobileDrawer — slide-out navigation drawer for mobile.
 * Replaces sidebar on small screens (<md).
 *
 * Features:
 *   - Overlay backdrop
 *   - Slide-in from left
 *   - User info + nav items + logout
 *   - Closes on backdrop click or navigation
 */
import { useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useSaasAuthStore } from "../../features/auth/authStore";

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "首页", icon: "📊" },
  { path: "/query", label: "AI 对话", icon: "💬" },
  { path: "/poetry", label: "诗意空间", icon: "📝" },
  { path: "/jobs", label: "职位匹配", icon: "🎯" },
  { path: "/resume", label: "简历解析", icon: "📄" },
  { path: "/candidates", label: "候选人", icon: "👥" },
  { path: "/reports", label: "报表", icon: "📈" },
  { path: "/pricing", label: "定价", icon: "💎" },
  { path: "/settings/consent", label: "隐私设置", icon: "🔒" },
];

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const { user, logout } = useSaasAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  /** Close drawer on Escape key */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, handleKeyDown]);

  /** Navigate and close drawer */
  const handleNavigate = (path: string) => {
    navigate(path);
    onClose();
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
    onClose();
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 md:hidden"
        style={{
          backgroundColor: "var(--color-bg-overlay)",
          transition: "opacity var(--transition-normal)",
        }}
        onClick={onClose}
      />

      {/* Drawer panel */}
      <aside
        className="fixed top-0 left-0 bottom-0 z-50 flex flex-col md:hidden"
        style={{
          width: "280px",
          maxWidth: "calc(100vw - 56px)",
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-xl)",
          animation: "slideInLeft 250ms ease-out",
        }}
      >
        {/* Brand header */}
        <div
          style={{
            padding: "20px",
            borderBottom: "1px solid var(--color-border-light)",
          }}
        >
          <h2
            style={{
              fontSize: "var(--font-size-xl)",
              fontWeight: "var(--font-weight-bold)",
              color: "var(--color-primary)",
              margin: 0,
            }}
          >
            T 空间
          </h2>
          <p
            style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
              margin: "4px 0 0",
            }}
          >
            {user?.email || "未登录"}
          </p>
        </div>

        {/* Nav items */}
        <nav
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "8px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.path);
            return (
              <button
                key={item.path}
                onClick={() => handleNavigate(item.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 16px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: active
                    ? "var(--color-primary-light)"
                    : "transparent",
                  color: active
                    ? "var(--color-primary)"
                    : "var(--color-text-primary)",
                  fontSize: "var(--font-size-base)",
                  fontWeight: active
                    ? "var(--font-weight-semibold)"
                    : "var(--font-weight-normal)",
                  cursor: "pointer",
                  transition: "all var(--transition-fast)",
                  textAlign: "left",
                  width: "100%",
                }}
              >
                <span style={{ fontSize: "18px", flexShrink: 0 }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer — Logout */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--color-border-light)",
            paddingBottom: "env(safe-area-inset-bottom, 12px)",
          }}
        >
          <button
            onClick={handleLogout}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-danger)",
              background: "transparent",
              color: "var(--color-danger)",
              fontSize: "var(--font-size-sm)",
              fontWeight: "var(--font-weight-medium)",
              cursor: "pointer",
              transition: "all var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-danger-light)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            退出登录
          </button>
        </div>
      </aside>

      {/* Keyframes for slide-in animation (injected once) */}
      <style>{`
        @keyframes slideInLeft {
          from { transform: translateX(-100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}