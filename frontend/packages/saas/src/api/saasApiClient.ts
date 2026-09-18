/**
 * SaaS 统一 ApiClient — 所有 SaaS 页面应通过此工厂创建 client。
 * 401 时自动 logout，同步清除 saas-auth 与 looma_token。
 */
import { createApiClient, type ApiClient } from "@looma/shared-core";
import { useSaasAuthStore } from "../features/auth/authStore";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export function createSaasApiClient(
  overrides?: Partial<Parameters<typeof createApiClient>[0]>,
): ApiClient {
  return createApiClient({
    baseURL: API_BASE,
    getToken: () => useSaasAuthStore.getState().token,
    onUnauthorized: () => useSaasAuthStore.getState().logout(),
    ...overrides,
  });
}
