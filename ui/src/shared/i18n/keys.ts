/**
 * `MessageKey`: every dotted path that exists in locales/en.json, as a type.
 *
 * This is what makes a typo in `t("panel.stauts.idle")` a compile error rather than a string
 * that quietly renders itself. English is the reference because the catalogue test asserts the
 * other languages have exactly its key set.
 */

import type en from "../../../../locales/en.json";

type PluralCategoryKey = "zero" | "one" | "two" | "few" | "many" | "other";

// An object whose keys are all CLDR categories is a leaf: `common.points` is a key, and
// `common.points.one` is a form of it, not a key of its own.
type IsPluralLeaf<T> = [Exclude<keyof T, PluralCategoryKey>] extends [never] ? true : false;

type Paths<T> = {
  [K in keyof T & string]: T[K] extends string
    ? K
    : IsPluralLeaf<T[K]> extends true
      ? K
      : `${K}.${Paths<T[K]>}`;
}[keyof T & string];

export type MessageKey = Paths<typeof en>;
