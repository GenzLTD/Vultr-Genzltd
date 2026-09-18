import {
  PERSONALITY_FALLBACK_MAP,
  PERSONALITY_MAP,
} from "../constants/personality";
import type { PersonalityType, TraitKey } from "../types/planetx-game";

export function computePersonality(
  traitCounts: Partial<Record<TraitKey, number>> | Record<TraitKey, number>,
): PersonalityType {
  const entries = Object.entries(traitCounts) as [TraitKey, number][];
  entries.sort((a, b) => b[1] - a[1]);
  const topTwo = entries.slice(0, 2).map((e) => e[0]);
  const key = topTwo.join("_");
  return (
    PERSONALITY_MAP[key] ??
    PERSONALITY_FALLBACK_MAP[topTwo[0]] ??
    PERSONALITY_MAP["creative_social"]
  );
}

/** Restore full PersonalityType from backend name / JSON detail. */
export function hydratePersonality(
  typeName?: string | PersonalityType,
  detailRaw?: string,
): PersonalityType | undefined {
  if (detailRaw) {
    try {
      const parsed = JSON.parse(detailRaw) as PersonalityType;
      if (parsed?.name) return parsed;
    } catch {
      /* ignore */
    }
  }
  if (typeof typeName === "object" && typeName?.name) return typeName;
  if (typeof typeName === "string" && typeName) {
    for (const p of Object.values(PERSONALITY_MAP)) {
      if (p.name === typeName) return p;
    }
  }
  return undefined;
}
