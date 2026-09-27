/**
 * What format.ts pins: a number is written the way the reader's language writes it, the Intl
 * options handed in reach Intl, and a malformed locale tag lands on English instead of throwing
 * in the middle of a stats readout. A unit Intl does not sanction is the one input that does
 * throw -- the fallback swaps the locale, not the options -- and that is pinned here too.
 *
 * Russian separators are asserted as properties rather than as literals: ICU has moved the
 * Russian group separator between U+00A0 and U+202F, and a hard-coded space would fail on a Node
 * upgrade for a reason no reader would recognise.
 */

import { describe, expect, it } from "vitest";

import { createFormatters } from "./format";

const en = createFormatters("en");
const ru = createFormatters("ru");

describe("the Intl data this module stands on", () => {
  // small-icu answers in English for every locale it does not carry, which would make the
  // locale-sensitive assertions below pass without testing anything.
  it("is a full ICU build, so the locale actually changes the output", () => {
    expect(new Intl.NumberFormat("ru").format(1234.5)).not.toBe(
      new Intl.NumberFormat("en").format(1234.5),
    );
  });
});

describe("number", () => {
  it("groups and points an English number the English way", () => {
    expect(en.number(1234567.5)).toBe("1,234,567.5");
    expect(en.number(0)).toBe("0");
    expect(en.number(-42)).toBe("-42");
  });

  it("groups and points a Russian number the Russian way", () => {
    const value = ru.number(1234567.5);
    expect(value).not.toBe(en.number(1234567.5));
    // A comma for the decimal separator, a space of some width for the group separator.
    expect(value.slice(-2)).toBe(",5");
    expect(value).not.toContain(".");
    expect(value.replace(/\D/g, "")).toBe("12345675");
  });

  it("passes Intl options through", () => {
    expect(en.number(0.5, { minimumFractionDigits: 2 })).toBe("0.50");
    expect(en.number(1234, { useGrouping: false })).toBe("1234");
    expect(en.number(1234.5678, { maximumFractionDigits: 1 })).toBe("1,234.6");
  });

  it("keeps one locale's formatter out of another's, across the cache", () => {
    expect(en.number(1234.5)).toBe("1,234.5");
    expect(ru.number(1234.5)).not.toBe("1,234.5");
    expect(en.number(1234.5)).toBe("1,234.5");
  });
});

describe("coordinate", () => {
  it("never groups, in any language", () => {
    expect(en.coordinate(1280)).toBe("1280");
    expect(ru.coordinate(1280)).toBe("1280");
    expect(en.coordinate(12800)).toBe("12800");
  });

  it("writes whole pixels, including left of or above the primary screen", () => {
    expect(en.coordinate(1279.6)).toBe("1280");
    expect(en.coordinate(-1920)).toBe("-1920");
    expect(en.coordinate(0)).toBe("0");
  });
});

describe("percent", () => {
  it("reads its argument as a fraction", () => {
    expect(en.percent(0)).toBe("0%");
    expect(en.percent(0.75)).toBe("75%");
    expect(en.percent(1)).toBe("100%");
  });

  it("takes a digit count, defaulting to none", () => {
    expect(en.percent(0.1234)).toBe("12%");
    expect(en.percent(0.1234, 1)).toBe("12.3%");
    expect(en.percent(0.5, 2)).toBe("50.00%");
  });

  it("writes the percent the way the language writes it", () => {
    const value = ru.percent(0.75);
    expect(value).not.toBe(en.percent(0.75));
    expect(value.endsWith("%")).toBe(true);
    expect(value.replace(/\D/g, "")).toBe("75");
  });
});

describe("unit", () => {
  it("appends the unit in short form", () => {
    expect(en.unit(5, "meter")).toBe("5 m");
    expect(en.unit(1234, "byte")).toBe("1,234 byte");
  });

  it("takes a digit count, defaulting to none", () => {
    expect(en.unit(12.34, "meter")).toBe("12 m");
    expect(en.unit(12.34, "meter", 1)).toBe("12.3 m");
  });

  it("lets an unsanctioned unit throw instead of inventing a reading for it", () => {
    // The fallback in formatter() re-uses the options, so `style: "unit"` with a bad `unit` fails
    // the same way twice. Nothing outside this repo chooses the string, so the throw stays a typo.
    expect(() => en.unit(5, "bogus")).toThrow(RangeError);
    // And it is contained: the throw leaves nothing broken behind in the shared formatter cache.
    expect(en.unit(5, "meter")).toBe("5 m");
  });

  it("writes the unit in the reader's language", () => {
    // The Russian abbreviation is Cyrillic, so this asserts that it differs rather than what it is.
    expect(ru.unit(5, "meter")).not.toBe(en.unit(5, "meter"));
    expect(ru.unit(5, "meter").replace(/\D/g, "")).toBe("5");
  });
});

describe("a locale tag Intl cannot parse", () => {
  it("falls back to English rather than throwing", () => {
    // An underscore is not a BCP 47 separator, so Intl throws on "ru_RU".
    const broken = createFormatters("ru_RU");
    expect(broken.number(1234567.5)).toBe(en.number(1234567.5));
    expect(broken.percent(0.75)).toBe(en.percent(0.75));
    expect(broken.unit(5, "meter")).toBe(en.unit(5, "meter"));
  });
});
