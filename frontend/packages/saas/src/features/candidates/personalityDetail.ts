/**
 * Parse personality_detail from referral profile view (shared by CandidateShare).
 */
import type { ProfileShareView } from "@looma/shared-core";

export interface PersonalityCard {
  name?: string;
  emoji?: string;
  tagline?: string;
  desc?: string;
  traits?: string[];
}

export function parsePersonalityDetail(view: ProfileShareView): PersonalityCard {
  const raw = view.personality_detail;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as PersonalityCard;
  }
  if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw) as PersonalityCard;
      if (parsed && typeof parsed === "object") return parsed;
    } catch {
      /* fall through */
    }
  }
  return { name: view.personality_type ?? "未知类型" };
}
