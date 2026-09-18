import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { createApiClient } from "./ApiClient";
import { createReferralApi } from "./createApi";
import { API_ROUTES } from "../constants/routes";

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "content-type" ? "application/json" : null,
    },
    json: async () => data,
  };
}

describe("ApiClient", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    const store: Record<string, string> = {};
    vi.stubGlobal("localStorage", {
      getItem(key: string) {
        return store[key] ?? null;
      },
      setItem(key: string, value: string) {
        store[key] = value;
      },
      removeItem(key: string) {
        delete store[key];
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches Authorization header when token is set", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    const client = createApiClient({
      baseURL: "http://127.0.0.1:5200",
      getToken: () => "test-jwt",
    });

    await client.get("/v1/game/profile");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toMatchObject({
      Authorization: "Bearer test-jwt",
    });
  });

  it("calls onUnauthorized when server returns 401", async () => {
    const onUnauthorized = vi.fn();
    fetchMock.mockResolvedValue(
      jsonResponse({ error: "unauthorized" }, 401),
    );

    const client = createApiClient({
      baseURL: "http://127.0.0.1:5200",
      getToken: () => "expired",
      onUnauthorized,
    });

    await expect(client.get("/v1/auth/profile")).rejects.toBeTruthy();
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});

describe("createReferralApi", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("localStorage", {
      getItem() {
        return null;
      },
      setItem() {},
      removeItem() {},
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("profileView hits public profile endpoint without auth", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        share_code: "ABC123",
        user_display: "Tester",
        personality_type: "星云艺术家",
        level: 1,
        xp: 0,
      }),
    );

    const client = createApiClient({ baseURL: "http://127.0.0.1:5200" });
    const api = createReferralApi(client);
    const view = await api.profileView("abc123");

    expect(view.personality_type).toBe("星云艺术家");
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain(`${API_ROUTES.REFERRAL_PROFILE_VIEW}/abc123`);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).not.toHaveProperty("Authorization");
  });

  it("create sends profile_share purpose in body", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: "XYZ789", purpose: "profile_share" }),
    );

    const client = createApiClient({
      baseURL: "http://127.0.0.1:5200",
      getToken: () => "jwt",
    });
    const api = createReferralApi(client);
    const resp = await api.create({ purpose: "profile_share" });

    expect(resp.code).toBe("XYZ789");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ purpose: "profile_share" });
  });
});
