/**
 * What locale.ts pins: the `auto | en | ru` setting turns into a language that actually shipped --
 * the same rule `resolve_language` applies in src/map_overlay/i18n/catalog.py -- and a language is
 * offered in its own name, with a capital, rather than in English.
 *
 * The Russian endonym is Cyrillic, which the repo's language gate keeps out of a .ts file, so it
 * is asserted by property: that it is what Intl says, that it is Cyrillic, that it is not the
 * English name, and that its first letter was raised. Those catch more than the word would.
 */

import { describe, expect, it } from "vitest";

import { FALLBACK_LOCALE, languageName, resolveLocale } from "./locale";

const AVAILABLE = ["en", "ru"] as const;
const CYRILLIC = /[\u0400-\u04FF]/;

function endonym(code: string): string {
  const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
  if (!name) throw new Error(`Intl has no name for ${code}`);
  return name;
}

describe("the Intl data this module stands on", () => {
  // small-icu carries English only and answers "German" for `de`, which would let the endonym
  // assertions below pass while the language selector showed English names to everyone.
  it("is a full ICU build, so a language can name itself", () => {
    expect(endonym("de")).toBe("Deutsch");
  });
});

describe("resolveLocale", () => {
  it("takes an explicit setting that shipped", () => {
    expect(resolveLocale("ru", "en-US", AVAILABLE)).toBe("ru");
    expect(resolveLocale("en", "ru-RU", AVAILABLE)).toBe("en");
  });

  it("falls back when the explicit setting never shipped", () => {
    expect(resolveLocale("de", "de-DE", AVAILABLE)).toBe(FALLBACK_LOCALE);
    expect(resolveLocale("", "ru-RU", AVAILABLE)).toBe(FALLBACK_LOCALE);
  });

  it("reads `auto` off the browser, however the tag is spelled", () => {
    for (const tag of ["ru", "ru-RU", "ru_RU", "RU", "ru-Cyrl-RU"]) {
      expect(resolveLocale("auto", tag, AVAILABLE), tag).toBe("ru");
    }
  });

  it("falls back when `auto` finds a language that never shipped", () => {
    expect(resolveLocale("auto", "de-DE", AVAILABLE)).toBe(FALLBACK_LOCALE);
    expect(resolveLocale("auto", "", AVAILABLE)).toBe(FALLBACK_LOCALE);
    expect(resolveLocale("auto", "ru-RU", ["en"])).toBe(FALLBACK_LOCALE);
  });

  it("never answers `auto`", () => {
    expect(resolveLocale("auto", "en-US", AVAILABLE)).not.toBe("auto");
    expect(resolveLocale("auto", "xx", AVAILABLE)).not.toBe("auto");
  });

  it("falls back to English", () => {
    expect(FALLBACK_LOCALE).toBe("en");
  });
});

describe("languageName", () => {
  it("names a language in its own language, not in English", () => {
    expect(languageName("en")).toBe("English");
    expect(languageName("de")).toBe("Deutsch");
    // French writes its own name in lower case; the selector shows a button label.
    expect(languageName("fr")).toBe("Français");
  });

  it("offers Russian in Cyrillic rather than as the English word", () => {
    const name = languageName("ru");
    expect(CYRILLIC.test(name)).toBe(true);
    expect(name).not.toBe(new Intl.DisplayNames(["en"], { type: "language" }).of("ru"));
  });

  it("raises the first letter, and only the first", () => {
    const raw = endonym("ru");
    const name = languageName("ru");
    // Intl hands Russian back in lower case, so the raise has to be visible here.
    expect(raw.charAt(0)).not.toBe(name.charAt(0));
    expect(name.charAt(0)).toBe(raw.charAt(0).toLocaleUpperCase("ru"));
    expect(name.slice(1)).toBe(raw.slice(1));
  });

  it("raises it the way the language raises it", () => {
    for (const code of ["en", "de", "fr", "ru"]) {
      const raw = endonym(code);
      expect(languageName(code), code).toBe(raw.charAt(0).toLocaleUpperCase(code) + raw.slice(1));
    }
  });

  it("gives back the code when Intl cannot parse it", () => {
    expect(languageName("!!")).toBe("!!");
    expect(languageName("")).toBe("");
  });

  it("gives back a well-formed code Intl has no name for", () => {
    expect(languageName("zz")).toBe("Zz");
  });
});
