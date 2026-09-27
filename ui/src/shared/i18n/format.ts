/**
 * Numbers in the reader's locale, with the Intl objects cached.
 *
 * The panel re-renders its stats at the engine's tick rate, and constructing an
 * Intl.NumberFormat per frame is measurably worse than keeping a handful of them.
 */

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(locale: string, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const cacheKey = `${locale}|${JSON.stringify(options)}`;
  const cached = formatters.get(cacheKey);
  if (cached) return cached;
  let made: Intl.NumberFormat;
  try {
    made = new Intl.NumberFormat(locale, options);
  } catch {
    // Only the locale differs here: bad options would throw again, so the retry rescues a
    // malformed tag and nothing else.
    made = new Intl.NumberFormat("en", options);
  }
  formatters.set(cacheKey, made);
  return made;
}

export interface Formatters {
  number: (value: number, options?: Intl.NumberFormatOptions) => string;
  coordinate: (value: number) => string;
  percent: (value: number, digits?: number) => string;
  unit: (value: number, unit: string, digits?: number) => string;
}

export function createFormatters(locale: string): Formatters {
  return {
    number: (value, options = {}) => formatter(locale, options).format(value),
    // A screen position in whole pixels, never grouped: two of them are written as a pair, and
    // "1,280, 0" reads as three numbers where "1280, 0" reads as two.
    coordinate: (value) =>
      formatter(locale, { useGrouping: false, maximumFractionDigits: 0 }).format(value),
    // `value` is a fraction: 0.75 reads as 75%.
    percent: (value, digits = 0) =>
      formatter(locale, {
        style: "percent",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value),
    // A unit outside Intl's sanctioned set throws RangeError, and the retry above cannot rescue
    // it -- that retry swaps the locale, not the options. Every call site passes a literal, so
    // such a throw is a typo in this repo, not something a user or the backend can cause.
    unit: (value, unit, digits = 0) =>
      formatter(locale, {
        style: "unit",
        unit,
        unitDisplay: "short",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value),
  };
}
