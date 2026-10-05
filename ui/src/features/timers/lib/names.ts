import type { MessageKey, TFunction } from "@/shared/i18n";

import type { TimerNow } from "./model";

/**
 * A timer's name as the player reads it. Events and bosses keep the game client's own spelling,
 * which is never translated; the two resets are ours to name, so they come from the catalogue.
 */
export function timerName(timer: Pick<TimerNow, "id" | "name">, t: TFunction): string {
  if (timer.id === "daily-reset") return t("timers.reset.daily");
  if (timer.id === "weekly-reset") return t("timers.reset.weekly");
  return timer.name;
}

const REGIONS: Readonly<Record<string, MessageKey>> = {
  "global-nae": "timers.region.nae",
  "global-naw": "timers.region.naw",
  "global-eu": "timers.region.eu",
  "global-sa": "timers.region.sa",
  "global-as": "timers.region.as",
  kr: "timers.region.kr",
  tw: "timers.region.tw",
};

/** A server region in the reader's language; a region a newer schedule adds keeps its label. */
export function regionName(region: { id: string; label: string }, t: TFunction): string {
  const key = REGIONS[region.id];
  return key ? t(key) : region.label;
}
