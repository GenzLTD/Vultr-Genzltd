/**
 * Closed-loop funnel event names (sync with backend VALID_EVENTS).
 */
import type { ClosedLoopEventName } from "../types/analytics";

export const CLOSED_LOOP_EVENTS: Record<string, ClosedLoopEventName> = {
  QUIZ_COMPLETE: "quiz_complete",
  SHARE_CODE_CREATED: "share_code_created",
  SHARE_LINK_COPIED: "share_link_copied",
  PROFILE_VIEW_PUBLIC: "profile_view_public",
  HR_REGISTER_FROM_SHARE: "hr_register_from_share",
  CANDIDATE_IMPORTED: "candidate_imported",
  TRIAL_STARTED: "trial_started",
  TRIAL_CLICKED: "trial_clicked",
} as const;

/**
 * 支付漏斗（海外会员）：看到价格 → 点订阅 → 进收银台 → 付款成功。
 *
 * 与后端 VALID_EVENTS 同步。前四个由客户端采集；
 * PAYMENT_SUCCEEDED 由**服务端**在结算成功后写入（前端不可信）。
 */
export const PAYMENT_FUNNEL_EVENTS: Record<string, ClosedLoopEventName> = {
  PRICING_VIEWED: "pricing_viewed",
  SUBSCRIBE_CLICKED: "subscribe_clicked",
  CHECKOUT_REDIRECTED: "checkout_redirected",
  CHECKOUT_FAILED: "checkout_failed",
  PAYMENT_SUCCEEDED: "payment_succeeded",
} as const;

export const ANALYTICS_SESSION_KEY = "looma_analytics_session";

export const MICRO_FEEDBACK_CONTEXT = {
  PLANETX_RESULT: "planetx_result",
  TSPACE_PROFILE_SHARE: "tspace_profile_share",
  TSPACE_PRICING: "tspace_pricing",
} as const;
