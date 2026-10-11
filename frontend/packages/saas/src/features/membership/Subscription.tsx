/**
 * Membership — 海外独立站虚拟会员订阅（诗词门户 / PlanetX 海外版）
 *
 * 复用后端 /v1/membership/*（Stripe + Stripe Tax，香港主体 YEDALL LIMITED）。
 * 回调 URL 运行时取自 window.location.origin（与 Pricing.tsx 同一契约，
 * 不在前端硬编码 genz.ltd 等域）。
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";
import { IS_OVERSEAS } from "../../config/region";

interface MembershipPlan {
  tier: string;
  name: string;
  price_monthly: number;
  currency: string;
  region: string;
  plan_id: string;
  features: string[];
  upgradable: boolean;
  billing_entity: string;
  entitlements: string[];
  quota: Record<string, number>;
}

interface MembershipPlansResponse {
  region: string;
  currency: string;
  billing_entity: string;
  tax: {
    engine: string;
    automatic_tax_enabled: boolean;
    tax_behavior: string;
    tax_code: string;
    tax_id_collection: boolean;
    note: string;
  };
  payment_methods: string[];
  plans: MembershipPlan[];
}

interface PlanCard extends MembershipPlan {
  desc: string;
  highlight: boolean;
  badge?: string;
  actionLabel: string;
}

const PLAN_META_US: Record<string, Pick<PlanCard, "desc" | "highlight" | "badge" | "actionLabel">> = {
  free: {
    desc: "Free forever — explore AI career tools",
    highlight: false,
    badge: "Free",
    actionLabel: "Get started free",
  },
  supporter: {
    desc: "Support the project and unlock higher limits",
    highlight: false,
    badge: "Supporter",
    actionLabel: "Subscribe",
  },
  pro: {
    desc: "Full AI power for serious career growth",
    highlight: true,
    badge: "Most popular",
    actionLabel: "Subscribe",
  },
};

const PLAN_META_CN: Record<string, Pick<PlanCard, "desc" | "highlight" | "badge" | "actionLabel">> = {
  free: {
    desc: "永久免费 —— 探索 AI 职业工具",
    highlight: false,
    badge: "免费",
    actionLabel: "免费开始",
  },
  supporter: {
    desc: "支持项目发展，解锁更高配额",
    highlight: false,
    badge: "支持者",
    actionLabel: "订阅",
  },
  pro: {
    desc: "释放 AI 全部能力，助力职业成长",
    highlight: true,
    badge: "最受欢迎",
    actionLabel: "订阅",
  },
};

const PLAN_META = IS_OVERSEAS ? PLAN_META_US : PLAN_META_CN;

function formatPrice(plan: MembershipPlan): string {
  if (plan.price_monthly === 0) return plan.currency === "USD" ? "$0" : "¥0";
  const symbol = plan.currency === "USD" ? "$" : "¥";
  return `${symbol}${plan.price_monthly}/mo`;
}

export default function Subscription() {
  const { isAuthenticated, token, fetchProfile } = useSaasAuthStore();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [plans, setPlans] = useState<PlanCard[]>([]);
  const [tax, setTax] = useState<MembershipPlansResponse["tax"] | null>(null);
  const [billingEntity, setBillingEntity] = useState("YEDALL LIMITED");
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [subscribingTier, setSubscribingTier] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const client = createSaasApiClient();
        const resp = await client.get<MembershipPlansResponse>("/v1/membership/plans");
        if (cancelled) return;
        const cards: PlanCard[] = resp.plans.map((plan) => ({
          ...plan,
          ...PLAN_META[plan.tier],
        }));
        setPlans(cards);
        setTax(resp.tax ?? null);
        setBillingEntity(resp.billing_entity ?? "YEDALL LIMITED");
      } catch {
        if (!cancelled) setMessage(IS_OVERSEAS ? "Unable to load plans. Please try again later." : "无法加载套餐，请稍后重试");
      } finally {
        if (!cancelled) setLoadingPlans(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const outcome = searchParams.get("status");
    if (outcome !== "success" && outcome !== "cancel") return;
    if (!token) return;

    if (outcome === "cancel") {
      setMessage(IS_OVERSEAS ? "Checkout cancelled." : "已取消支付");
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const client = createSaasApiClient();
        const status = await client.get<{ tier: string; status: string; plan?: { name: string } }>(
          "/v1/membership/status",
        );
        await fetchProfile();
        if (cancelled) return;
        if (status.tier !== "free" && status.status !== "inactive") {
          setMessage(IS_OVERSEAS ? `Membership activated: ${status.tier}.` : `会员已开通：${status.tier}`);
        } else {
          setMessage(
            IS_OVERSEAS
              ? "Payment received. Refresh if your plan has not updated yet."
              : "已返回，档位更新可能稍有延迟，请刷新页面。",
          );
        }
      } catch {
        if (!cancelled) {
          setMessage(IS_OVERSEAS ? "Could not refresh membership status. Please reload." : "无法刷新会员状态，请刷新页面。");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams, token, fetchProfile]);

  const handleSubscribe = async (tier: "supporter" | "pro") => {
    if (!isAuthenticated || !token) {
      navigate(`/register?from=subscribe`);
      return;
    }

    setSubscribingTier(tier);
    setMessage(null);

    try {
      const client = createSaasApiClient();
      const checkout = await client.post<{ checkout_url: string }>("/v1/membership/subscribe", {
        tier,
        // 运行时回调：浏览器 origin，不在前端硬编码域（与 Pricing.tsx 同契约）
        success_url: `${window.location.origin}/subscribe?status=success`,
        cancel_url: `${window.location.origin}/subscribe?status=cancel`,
      });
      window.location.href = checkout.checkout_url;
    } catch (err: any) {
      const status = err?.status ?? err?.body?.status;
      if (status === 400 && err?.body?.error === "stub_mode") {
        setMessage(
          IS_OVERSEAS
            ? "Checkout is disabled in stub mode. Set PAYMENT_STUB_MODE=false to enable Stripe."
            : "当前为 Stub 模式，收银台关闭。请设置 PAYMENT_STUB_MODE=false 启用 Stripe。",
        );
      } else if (status === 503) {
        setMessage(IS_OVERSEAS ? "Payment not configured. Please contact support." : "支付未配置，请联系管理员开通");
      } else {
        setMessage(IS_OVERSEAS ? "Something went wrong. Please try again." : "操作失败，请稍后重试");
      }
    } finally {
      setSubscribingTier(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto" style={{ paddingTop: "1rem" }}>
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold mb-3" style={{ color: "var(--color-text-primary)" }}>
          {IS_OVERSEAS ? "Membership" : "海外会员"}
        </h1>
        <p className="text-sm max-w-md mx-auto" style={{ color: "var(--color-text-secondary)", lineHeight: 1.8 }}>
          {IS_OVERSEAS
            ? "Billed monthly in USD · Cancel anytime"
            : "按月美元计费 · 随时取消"}
        </p>
        {billingEntity && (
          <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
            {IS_OVERSEAS ? `Billed by ${billingEntity}` : `账单主体：${billingEntity}`}
          </p>
        )}
      </div>

      {loadingPlans ? (
        <p className="text-center text-sm mb-10" style={{ color: "var(--color-text-muted)" }}>
          {IS_OVERSEAS ? "Loading plans…" : "加载套餐中…"}
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {plans.map((plan) => {
            const bullets = plan.entitlements?.length ? plan.entitlements : plan.features;
            return (
              <div
                key={plan.tier}
                className="rounded-xl p-6 flex flex-col relative transition-shadow hover:shadow-lg"
                style={{
                  backgroundColor: "var(--color-bg-card)",
                  boxShadow: plan.highlight ? "0 0 0 2px var(--color-primary), var(--shadow-md)" : "var(--shadow-sm)",
                  transform: plan.highlight ? "scale(1.03)" : "scale(1)",
                }}
              >
                {plan.badge && (
                  <span
                    className="absolute -top-3 left-6 px-3 py-0.5 rounded-full text-xs font-medium text-white"
                    style={{ backgroundColor: plan.highlight ? "var(--color-primary)" : "var(--color-text-muted)" }}
                  >
                    {plan.badge}
                  </span>
                )}

                <h3 className="text-lg font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
                  {plan.name}
                </h3>
                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-3xl font-bold" style={{ color: "var(--color-primary)" }}>
                    {formatPrice(plan)}
                  </span>
                </div>
                <p className="text-xs mb-5" style={{ color: "var(--color-text-muted)" }}>{plan.desc}</p>

                <div className="mb-5" style={{ height: 1, backgroundColor: "var(--color-border)" }} />

                <ul className="flex-1 space-y-3 mb-6">
                  {bullets.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                      <span style={{ color: "var(--color-success)", flexShrink: 0 }}>✓</span>
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => void handleSubscribe(plan.tier as "supporter" | "pro")}
                  disabled={subscribingTier !== null}
                  className="w-full py-2.5 text-sm rounded-lg font-medium text-white disabled:opacity-60"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  {subscribingTier === plan.tier
                    ? (IS_OVERSEAS ? "Processing…" : "处理中…")
                    : plan.actionLabel}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {message && (
        <p className="text-center text-sm mb-4" style={{ color: "var(--color-success)" }}>{message}</p>
      )}

      <div
        className="text-center rounded-xl p-6"
        style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
      >
        <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
          {IS_OVERSEAS ? "💳 Stripe Checkout" : "💳 Stripe 收银台"}
        </p>
        <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
          {IS_OVERSEAS
            ? "Supporter $1.99/mo · Pro $5.99/mo · Card, Apple Pay, Google Pay"
            : "支持者 $1.99/月 · 专业版 $5.99/月 · 银行卡 / Apple Pay / Google Pay"}
        </p>
        {tax?.note && (
          <p className="text-xs mb-2 max-w-lg mx-auto" style={{ color: "var(--color-text-muted)" }}>
            {tax.note}
          </p>
        )}
        {!isAuthenticated && (
          <Link to="/register" className="text-sm" style={{ color: "var(--color-primary)" }}>
            {IS_OVERSEAS ? "No account yet? Sign up →" : "还没有账号？立即注册 →"}
          </Link>
        )}
      </div>
    </div>
  );
}
