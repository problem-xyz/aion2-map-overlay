/**
 * What plural.ts pins: which CLDR *category* a count takes, and that the browser's answer is the
 * one `_plural_category` in src/map_overlay/i18n/catalog.py gives. Both sides pick forms out of
 * the same locales/*.json, so a disagreement would put the wrong Russian ending on screen in the
 * half of the app the other language owns.
 *
 * Categories are asserted by name, never by a translated word: the word belongs to a catalogue
 * test, the category is what this module decides.
 */

import { describe, expect, it } from "vitest";

import { isPluralLeaf, pluralCategory, type PluralCategory } from "./plural";

// A transcription of `_plural_category` in src/map_overlay/i18n/catalog.py, so that the agreement
// test below compares against Python's actual rule rather than against a second guess at CLDR.
function pythonCategory(language: string, count: number): PluralCategory {
  const n = Math.abs(count);
  if (language === "ru") {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return "one";
    if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) return "few";
    return "many";
  }
  return n === 1 ? "one" : "other";
}

describe("the Intl data this module stands on", () => {
  // A Node built with small-icu knows English and answers "other" for everything else, which would
  // make every assertion below pass without testing anything. Fail loudly on such a build instead.
  it("is a full ICU build, so the categories below are real answers", () => {
    expect([...new Intl.PluralRules("ru").resolvedOptions().pluralCategories].sort()).toEqual([
      "few",
      "many",
      "one",
      "other",
    ]);
  });
});

describe("pluralCategory", () => {
  it("gives English its two forms", () => {
    expect(pluralCategory("en", 0)).toBe("other");
    expect(pluralCategory("en", 1)).toBe("one");
    expect(pluralCategory("en", 2)).toBe("other");
    expect(pluralCategory("en", 21)).toBe("other");
  });

  it("gives Russian its four forms, including the 11-14 and the 101/111 exceptions", () => {
    const expected: [number, PluralCategory][] = [
      [1, "one"],
      [2, "few"],
      [5, "many"],
      [11, "many"],
      [21, "one"],
      [22, "few"],
      [25, "many"],
      [101, "one"],
      [111, "many"],
    ];
    for (const [count, category] of expected) {
      expect(pluralCategory("ru", count), `ru ${count}`).toBe(category);
    }
  });

  it("agrees with the hand-written Python rule for every count from 0 to 1000", () => {
    const disagreements: string[] = [];
    for (const locale of ["en", "ru"]) {
      for (let count = 0; count <= 1000; count += 1) {
        const browser = pluralCategory(locale, count);
        const python = pythonCategory(locale, count);
        if (browser !== python) {
          disagreements.push(`${locale} ${count}: Intl=${browser} Python=${python}`);
        }
      }
    }
    expect(disagreements).toEqual([]);
  });

  it("keeps one language's rules out of another's, across the cache", () => {
    expect(pluralCategory("ru", 2)).toBe("few");
    expect(pluralCategory("en", 2)).toBe("other");
    expect(pluralCategory("ru", 2)).toBe("few");
  });

  it("answers `other` for a count that is not a finite number", () => {
    expect(pluralCategory("ru", Number.NaN)).toBe("other");
    expect(pluralCategory("ru", Number.POSITIVE_INFINITY)).toBe("other");
    expect(pluralCategory("en", Number.NEGATIVE_INFINITY)).toBe("other");
  });

  it("falls back to the English rule when Intl cannot parse the tag", () => {
    // An underscore is not a BCP 47 separator, so Intl throws on "ru_RU": the answers that come
    // back are English ones, which is the point -- a bad tag must not take a list render down.
    expect(pluralCategory("ru_RU", 1)).toBe("one");
    expect(pluralCategory("ru_RU", 2)).toBe("other");
    expect(pluralCategory("ru_RU", 5)).toBe("other");
  });
});

describe("isPluralLeaf", () => {
  it("accepts an object whose keys are all CLDR categories", () => {
    expect(isPluralLeaf({ one: "a", other: "b" })).toBe(true);
    expect(isPluralLeaf({ one: "a", few: "b", many: "c", other: "d" })).toBe(true);
    expect(isPluralLeaf({ other: "b" })).toBe(true);
  });

  it("rejects a branch, so a catalogue can nest by area without a marker", () => {
    expect(isPluralLeaf({ idle: "a", running: "b" })).toBe(false);
    expect(isPluralLeaf({ status: { idle: "a" } })).toBe(false);
  });

  it("rejects a branch that happens to hold a category name", () => {
    expect(isPluralLeaf({ one: "a", title: "b" })).toBe(false);
  });

  it("rejects an empty object, which carries no form to choose", () => {
    expect(isPluralLeaf({})).toBe(false);
  });
});
