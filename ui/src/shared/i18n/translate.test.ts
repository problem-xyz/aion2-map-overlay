import { describe, expect, it, vi } from "vitest";

import type { Catalog } from "./catalogs";
import { createT } from "./translate";

const en: Catalog = new Map<string, string | Record<string, string>>([
  ["a.plain", "Stopped"],
  ["a.named", "Route “{name}” saved."],
  ["a.count", { one: "{count} point", other: "{count} points" }],
  ["a.onlyEnglish", "English only"],
]);

// The forms are ASCII on purpose: this asserts which CLDR *category* Russian selects, and the
// words would only be Cyrillic that the language gate then has to make an exception for. The
// real Russian wording is asserted against the shipped catalogue in tests/test_i18n_catalog.py.
const ru: Catalog = new Map<string, string | Record<string, string>>([
  ["a.plain", "ru-plain"],
  ["a.named", "ru-named {name}"],
  ["a.count", { one: "{count} ru-one", few: "{count} ru-few", many: "{count} ru-many" }],
]);

function make(locale: string, catalog: Catalog, onMissing?: (key: string) => void) {
  return createT({
    locale,
    catalog,
    fallback: en,
    formatNumber: (value) => String(value),
    onMissing,
  });
}

describe("createT", () => {
  it("returns the sentence for the chosen language", () => {
    expect(make("ru", ru)("a.plain" as never)).toBe("ru-plain");
    expect(make("en", en)("a.plain" as never)).toBe("Stopped");
  });

  it("falls back to English when the language lacks the key", () => {
    expect(make("ru", ru)("a.onlyEnglish" as never)).toBe("English only");
  });

  it("returns the key itself when nothing has it, and says so once", () => {
    const onMissing = vi.fn();
    expect(make("ru", ru, onMissing)("a.nothing" as never)).toBe("a.nothing");
    expect(onMissing).toHaveBeenCalledWith("a.nothing");
  });

  it("interpolates named parameters", () => {
    expect(make("en", en)("a.named" as never, { name: "Altgard" })).toBe("Route “Altgard” saved.");
  });

  it("leaves an unfilled placeholder visible rather than blanking it", () => {
    expect(make("en", en)("a.named" as never)).toBe("Route “{name}” saved.");
  });

  it("picks the English plural form from count", () => {
    const t = make("en", en);
    expect(t("a.count" as never, { count: 1 })).toBe("1 point");
    expect(t("a.count" as never, { count: 4 })).toBe("4 points");
  });

  it("picks the Russian plural form from count, including the 11-14 exception", () => {
    const t = make("ru", ru);
    expect(t("a.count" as never, { count: 1 })).toBe("1 ru-one");
    expect(t("a.count" as never, { count: 2 })).toBe("2 ru-few");
    expect(t("a.count" as never, { count: 5 })).toBe("5 ru-many");
    expect(t("a.count" as never, { count: 11 })).toBe("11 ru-many");
    expect(t("a.count" as never, { count: 21 })).toBe("21 ru-one");
  });

  it("uses `other` when a plural key is used without a count", () => {
    expect(make("en", en)("a.count" as never)).toBe("{count} points");
  });

  it("formats numeric parameters through the locale formatter", () => {
    const t = createT({
      locale: "en",
      catalog: en,
      fallback: en,
      formatNumber: (value) => `<${value}>`,
    });
    expect(t("a.count" as never, { count: 3 })).toBe("<3> points");
  });
});
