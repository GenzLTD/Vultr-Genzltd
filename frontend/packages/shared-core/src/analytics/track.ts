/**
 * Client-side product analytics — fire-and-forget batch to backend.
 */
import type { AnalyticsPlatform, ClosedLoopEventName } from "../types/analytics";
import { ANALYTICS_SESSION_KEY } from "../constants/analytics";
import type { ApiClient } from "../api/ApiClient";
import { API_ROUTES } from "../constants/routes";

let _client: ApiClient | null = null;
let _platform: AnalyticsPlatform = "unknown";
const _queue: Array<Record<string, unknown>> = [];
let _flushTimer: ReturnType<typeof setTimeout> | null = null;

export function initAnalytics(client: ApiClient, platform: AnalyticsPlatform): void {
  _client = client;
  _platform = platform;
}

export function getAnalyticsSessionId(): string {
  if (typeof localStorage === "undefined") {
    return `sess_${Date.now()}`;
  }
  let id = localStorage.getItem(ANALYTICS_SESSION_KEY);
  if (!id) {
    id = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    localStorage.setItem(ANALYTICS_SESSION_KEY, id);
  }
  return id;
}

export function trackEvent(
  eventName: ClosedLoopEventName,
  props?: {
    share_code?: string;
    success?: boolean;
    properties?: Record<string, unknown>;
  },
): void {
  _queue.push({
    event_name: eventName,
    session_id: getAnalyticsSessionId(),
    platform: _platform,
    share_code: props?.share_code,
    success: props?.success ?? true,
    properties: props?.properties,
  });
  if (_flushTimer) return;
  _flushTimer = setTimeout(() => {
    _flushTimer = null;
    void flushEvents();
  }, 300);
}

export async function flushEvents(): Promise<void> {
  if (!_client || _queue.length === 0) return;
  const batch = _queue.splice(0, 50);
  try {
    await _client.post(API_ROUTES.ANALYTICS_EVENTS, { events: batch });
  } catch {
    /* best-effort */
  }
}

/** WeChat miniprogram: pass wx storage-backed session id */
export function getWxAnalyticsSessionId(getStorage: (key: string) => string | null, setStorage: (key: string, val: string) => void): string {
  let id = getStorage(ANALYTICS_SESSION_KEY);
  if (!id) {
    id = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    setStorage(ANALYTICS_SESSION_KEY, id);
  }
  return id;
}
