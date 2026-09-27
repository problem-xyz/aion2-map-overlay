/**
 * Looking a key up and filling it in.
 *
 * Three steps, in this order: the chosen language, then English, then the key itself. Showing
 * the key is deliberate -- it is obvious on screen and in a screenshot, where a silently empty
 * label is not, and it never takes a window down over a missing sentence.
 */

import type { Catalog, Message } from "./catalogs";
import type { MessageKey } from "./keys";
import { pluralCategory } from "./plural";

export type TParams = Record<string, string | number>;
export type TFunction = (key: MessageKey, params?: TParams) => string;

const PLACEHOLDER = /\{(\w+)\}/g;

/** Plural leaves choose on `count`; anything else is already the sentence. */
function form(message: Message, locale: string, params: TParams): string | undefined {
  if (typeof message === "string") return message;
  const count = params.count;
  const category = typeof count === "number" ? pluralCategory(locale, count) : "other";
  return message[category] ?? message.other;
}

export interface CreateTOptions {
  locale: string;
  catalog: Catalog;
  fallback: Catalog;
  formatNumber: (value: number) => string;
  onMissing?: (key: string) => void;
}

export function createT({
  locale,
  catalog,
  fallback,
  formatNumber,
  onMissing,
}: CreateTOptions): TFunction {
  return (key, params = {}) => {
    const message = catalog.get(key) ?? fallback.get(key);
    const template = message === undefined ? undefined : form(message, locale, params);
    if (template === undefined) {
      onMissing?.(key);
      return key;
    }
    return template.replace(PLACEHOLDER, (whole, name: string) => {
      const value = params[name];
      if (value === undefined) return whole; // an unfilled {slot} is louder than an empty gap
      return typeof value === "number" ? formatNumber(value) : value;
    });
  };
}
