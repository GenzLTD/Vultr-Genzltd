import type { PersonalityType } from "../types/planetx-game";

export type SharePlatform =
  | "wechat"
  | "xiaohongshu"
  | "weibo"
  | "copy"
  | "miniprogram";

const SHARE_TEMPLATES: Record<
  Exclude<SharePlatform, "miniprogram">,
  (p: PersonalityType, inviteUrl: string) => string
> = {
  wechat: (p, inviteUrl) =>
    `🪐 我的星际人格是「${p.name}」！\n"${p.tagline}"\n\n👉 测测你的是什么星球身份？\n${inviteUrl}`,
  xiaohongshu: (p, inviteUrl) =>
    `🪐 PlanetX 星际人格测试 🪐\n\n我的身份：${p.emoji} ${p.name}\n标签：#${p.traits.join(" #")}\n\n"${p.tagline}"\n\n${p.desc}\n\n#PlanetX #星际人格 #MBTI #Z世代 #求职\n🔗 ${inviteUrl}`,
  weibo: (p, inviteUrl) =>
    `🪐 PlanetX星际人格认证：我是「${p.name}」${p.emoji}\n"${p.tagline}"\n${p.desc.slice(0, 60)}…\n\n你也来测测？${inviteUrl}\n#PlanetX星际人格# #00后求职#`,
  copy: (p, inviteUrl) =>
    `🪐 我在 PlanetX 的星际人格是「${p.name}」！\n${p.tagline}\n\n扫码来测测你的星际身份 → ${inviteUrl}`,
};

/** Platform-specific share copy; miniprogram uses wechat-style template. */
export function getShareText(
  platform: SharePlatform,
  p: PersonalityType,
  inviteUrl: string,
): string {
  if (platform === "miniprogram") {
    return SHARE_TEMPLATES.wechat(p, inviteUrl);
  }
  return SHARE_TEMPLATES[platform](p, inviteUrl);
}
