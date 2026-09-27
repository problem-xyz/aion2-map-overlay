/**
 * Which plural form a count takes, asked of the platform rather than hand-written.
 *
 * Python has to spell the CLDR rules out (see i18n/catalog.py); the browser already knows them,
 * so a new language needs no code here at all -- only a locales/<lang>.json with the categories
 * that Intl says that language uses.
 */

export type PluralCategory = "zero" | "one" | "two" | "few" | "many" | "other";

/** A plural leaf in a catalogue: the categories a language actually uses, and nothing else. */
export type PluralForms = Partial<Record<PluralCategory, string>>;

// Intl.PluralRules costs real time to construct, and a list re-renders once per route.
const rules = new Map<string, Intl.PluralRules>();

function rulesFor(locale: string): Intl.PluralRules {
  const cached = rules.get(locale);
  if (cached) return cached;
  let made: Intl.PluralRules;
  try {
    made = new Intl.PluralRules(locale);
  } catch {
    made = new Intl.PluralRules("en");
  }
  rules.set(locale, made);
  return made;
}

export function pluralCategory(locale: string, count: number): PluralCategory {
  if (!Number.isFinite(count)) return "other";
  return rulesFor(locale).select(count);
}

const CATEGORIES = new Set<string>(["zero", "one", "two", "few", "many", "other"]);

/**
 * A nested object is a plural leaf when every key is a CLDR category. That is what lets a
 * catalogue nest by area without a marker: `panel.status` is a branch, `common.points` is a leaf.
 */
export function isPluralLeaf(value: object): boolean {
  const keys = Object.keys(value);
  return keys.length > 0 && keys.every((key) => CATEGORIES.has(key));
}
