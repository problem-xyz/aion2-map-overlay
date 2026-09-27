/** How many of the plaque's rows fit the height the user gave the window. */
export interface RowFit {
  /** The last this many of the steps passed are shown. */
  behind: number;
  /** The first this many of the steps ahead are shown. */
  ahead: number;
}

export interface RowHeights {
  /** The steps passed that may be shown, oldest first. */
  behind: readonly number[];
  /** The steps ahead that may be shown, nearest first. */
  ahead: readonly number[];
  /** How many steps are ahead in all: more than `ahead` holds when the route is long. */
  left: number;
  /** The "N more points" line, shown under the rows whenever a step ahead is left out. */
  more: number;
  /** The height the list has for all of them. */
  room: number;
  /** The steps passed give way before fewer than this many steps ahead are shown. */
  minAhead: number;
}

/**
 * The steps passed come first and the steps ahead after them, each whole or not at all; the
 * nearest step is shown even when it does not fit, since a plaque without it says nothing. A
 * list that has not been laid out yet -- no room measured -- shows everything it was given.
 */
export function fitRows({ behind, ahead, left, more, room, minAhead }: RowHeights): RowFit {
  if (room <= 0) return { behind: behind.length, ahead: ahead.length };

  const aheadFitting = (shownBehind: number) => {
    let used = 0;
    for (let i = behind.length - shownBehind; i < behind.length; i++) used += behind[i] ?? 0;
    let count = 0;
    while (count < ahead.length) {
      const next = used + (ahead[count] ?? 0);
      // the line saying how many are left has to fit under the last row, unless none are left
      const reserve = count + 1 < left ? more : 0;
      if (next + reserve > room) break;
      used = next;
      count++;
    }
    return count;
  };

  let shownBehind = behind.length;
  let count = aheadFitting(shownBehind);
  const wanted = Math.min(minAhead, ahead.length);
  while (shownBehind > 0 && count < wanted) {
    shownBehind--;
    count = aheadFitting(shownBehind);
  }
  return { behind: shownBehind, ahead: Math.max(count, Math.min(1, ahead.length)) };
}
