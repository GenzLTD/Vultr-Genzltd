/**
 * Mini-program-safe API types and wx storage adapter.
 * Kept separate from ApiClient.ts to avoid pulling fetch/localStorage into the mini bundle.
 */

export interface StorageAdapter {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
}

export interface ApiClientConfig {
  baseURL: string;
  storage?: StorageAdapter;
  tokenKey?: string;
  getToken?: () => string | null | Promise<string | null>;
  onUnauthorized?: () => void;
  timeout?: number;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, any>;
  timeout?: number;
}

export class ApiError extends Error {
  status: number;
  body: Record<string, any>;

  constructor(status: number, body: Record<string, any>, message?: string) {
    super(message || body?.message || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

declare const wx: {
  getStorageSync(key: string): unknown;
  setStorageSync(key: string, data: string): void;
  removeStorageSync(key: string): void;
  request?: unknown;
} | undefined;

/** WeChat miniprogram wx.storage adapter. */
export function wxStorageAdapter(): StorageAdapter {
  const storage = typeof wx !== "undefined" ? wx : undefined;
  return {
    getItem: (key: string) => {
      try {
        return (storage?.getStorageSync(key) as string | null) ?? null;
      } catch {
        return null;
      }
    },
    setItem: (key: string, value: string) => {
      try {
        storage?.setStorageSync(key, value);
      } catch {
        /* ignore */
      }
    },
    removeItem: (key: string) => {
      try {
        storage?.removeStorageSync(key);
      } catch {
        /* ignore */
      }
    },
  };
}

export function isWechatMiniProgram(): boolean {
  return typeof wx !== "undefined" && typeof wx.request === "function";
}
