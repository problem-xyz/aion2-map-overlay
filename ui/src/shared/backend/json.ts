/** JSON parsing that cannot throw into a render. */

/**
 * Parse a payload from Python, or return the fallback.
 *
 * A malformed payload is a bug on the other side, and one bad frame of stats must not blank
 * the window. It is logged and dropped.
 */
export function safeParse<T>(text: string | null | undefined, fallback: T): T {
  if (typeof text !== "string" || text === "") return fallback;
  try {
    return JSON.parse(text) as T;
  } catch (e) {
    console.error("backend sent unparseable JSON", e, text.slice(0, 200));
    return fallback;
  }
}
