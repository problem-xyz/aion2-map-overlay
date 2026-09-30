import { useCallback, useState } from "react";

import type { Faction, RouteInfo } from "@/shared/backend/contract";

export type RouteFilter = "all" | Faction;

const FILTER_KEY = "mo.panel.routeFilter";
const FILTERS: readonly RouteFilter[] = ["all", "asmodian", "elyos"];

function loadFilter(): RouteFilter {
  try {
    const stored = window.localStorage.getItem(FILTER_KEY);
    return FILTERS.find((f) => f === stored) ?? "all";
  } catch {
    return "all";
  }
}

/** Is there a choice to make: routes of both sides in the list. */
export function hasBothFactions(routes: RouteInfo[]): boolean {
  return new Set(routes.flatMap((r) => r.faction ?? [])).size > 1;
}

/**
 * `ids`, the ids shown under a filter, put back into `all`: the places the shown rows held in the
 * whole list are filled in their new order, and every hidden row keeps its own place.
 */
export function mergeOrder(all: string[], ids: string[]): string[] {
  const shown = new Set(ids);
  let next = 0;
  return all.map((id) => (shown.has(id) ? (ids[next++] ?? id) : id));
}

/**
 * The faction the list is filtered to, remembered between runs. It applies only while the list
 * has routes of both sides: with one side there is nothing to choose, and a filter left on the
 * other would hide every route.
 */
export function useRouteFilter(routes: RouteInfo[]) {
  const [chosen, setChosen] = useState<RouteFilter>(loadFilter);
  const available = hasBothFactions(routes);
  const filter: RouteFilter = available ? chosen : "all";

  const setFilter = useCallback((next: RouteFilter) => {
    setChosen(next);
    try {
      window.localStorage.setItem(FILTER_KEY, next);
    } catch {
      /* private mode, or writes are forbidden -- the list opens unfiltered next time */
    }
  }, []);

  const visible = (list: RouteInfo[]) =>
    filter === "all" ? list : list.filter((r) => r.faction === filter);

  return { available, filter, setFilter, visible };
}
