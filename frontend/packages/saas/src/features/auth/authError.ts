/** Best-effort message from ApiError / fetch failures. */
export function messageFromAuthError(err: unknown, fallback: string): string {
  if (!err || typeof err !== "object") return fallback;
  const e = err as {
    detail?: string;
    message?: string;
    body?: { message?: string; detail?: string };
  };
  const msg = e.body?.message || e.body?.detail || e.detail || e.message;
  if (typeof msg === "string" && msg.trim()) return msg;
  return fallback;
}
