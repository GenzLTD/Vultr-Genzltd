/**
 * Brand constants and types.
 * Each brand package uses these to identify itself.
 */

export type BrandId = "planetx" | "saas";

export interface BrandConfig {
  id: BrandId;
  name: string;
  slogan: string;
  primaryColor: string;
  domain: string;
}

export const BRAND_PLANETX: BrandConfig = {
  id: "planetx",
  name: "PlanetX",
  slogan: "你的职业飞行器",
  primaryColor: "#6C63FF",
  domain: "127.0.0.1",  // TODO: ICP 备案后替换为正式域名
};

export const BRAND_SAAS: BrandConfig = {
  id: "saas",
  name: "T空间",
  slogan: "让 AI 成为你的招聘合伙人",
  primaryColor: "#1a6ff5",
  domain: "127.0.0.1",  // TODO: ICP 备案后替换为正式域名
};

export const BRAND = {
  PLANETX: BRAND_PLANETX,
  SAAS: BRAND_SAAS,
} as const;
