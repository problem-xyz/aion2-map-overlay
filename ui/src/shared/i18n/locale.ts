/**
 * Turning the `auto | en | ru` setting into a language that actually shipped.
 *
 * Kept apart from the provider so it can be tested without a DOM, and so the same rule is
 * readable next to `resolve_language` in i18n/catalog.py, which does this for the Qt side.
 */

export const FALLBACK_LOCALE = "en";

export function resolveLocale(
  setting: string,
  navigatorLanguage: string,
  available: readonly string[],
): string {
  if (setting !== "auto") {
    return available.includes(setting) ? setting : FALLBACK_LOCALE;
  }
  // "ru-RU", "ru_RU" and "ru" all mean the same catalogue to us.
  const short = navigatorLanguage.slice(0, 2).toLowerCase();
  return available.includes(short) ? short : FALLBACK_LOCALE;
}

/**
 * A language's name in its own language: English stays "English", German becomes "Deutsch",
 * and Russian is written in Cyrillic rather than transliterated.
 *
 * Asked of Intl rather than kept in the catalogues, for two reasons. A name written in en.json
 * would put Cyrillic in the English catalogue, which the language gate forbids for good reason;
 * and this way a new locales/<code>.json names itself in the selector without anyone adding a
 * string for it. Russian writes language names in lower case, so the first letter is raised for
 * a button label.
 */
export function languageName(code: string): string {
  try {
    const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
    if (!name) return code;
    return name.charAt(0).toLocaleUpperCase(code) + name.slice(1);
  } catch {
    return code;
  }
}
