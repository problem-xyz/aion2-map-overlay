/**
 * The language the app is speaking, and the two things every component needs from it.
 *
 * This provider sits above BackendProvider on purpose: the connection screens are the first
 * thing a user can see, and they have to be translated too. The first locale therefore comes
 * from navigator.language synchronously -- there is no state from Python yet -- and the
 * language setting replaces it once state arrives.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { available, catalogs, type Catalog } from "./catalogs";
import { createFormatters, type Formatters } from "./format";
import { FALLBACK_LOCALE, resolveLocale } from "./locale";
import { createT, type TFunction } from "./translate";

const EMPTY: Catalog = new Map();

export interface I18n {
  /** The language actually in use, always one that shipped: "en", never "auto". */
  locale: string;
  t: TFunction;
  format: Formatters;
  available: readonly string[];
  /** Takes the setting, not a locale: "auto" is resolved here. */
  setLanguage: (setting: string) => void;
}

const I18nContext = createContext<I18n | null>(null);

// One warning per key, not per render: a missing key in a list would otherwise fill the console
// and hide everything else. A built UI warns too -- Python's LoggingPage writes the page console
// to the app log, the one place a key missing from a shipped build can be found at all.
const warned = new Set<string>();

function reportMissing(key: string): void {
  if (warned.has(key)) return;
  warned.add(key);
  console.warn(`[i18n] no message for ${key}`);
}

export interface I18nProviderProps {
  children: ReactNode;
  /** Initial setting. The steps plaque is told its language by Python and passes it here. */
  initial?: string;
}

export function I18nProvider({ children, initial = "auto" }: I18nProviderProps) {
  const [setting, setLanguage] = useState(initial);

  useEffect(() => {
    setLanguage(initial);
  }, [initial]);

  const locale = useMemo(() => resolveLocale(setting, navigator.language, available), [setting]);

  const value = useMemo<I18n>(() => {
    const format = createFormatters(locale);
    return {
      locale,
      format,
      available,
      setLanguage,
      t: createT({
        locale,
        catalog: catalogs.get(locale) ?? EMPTY,
        fallback: catalogs.get(FALLBACK_LOCALE) ?? EMPTY,
        formatNumber: format.number,
        onMissing: reportMissing,
      }),
    };
  }, [locale]);

  // Screen readers and the browser's own hyphenation read this, and it is the one place the
  // chosen language is visible from outside React.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n outside I18nProvider");
  return value;
}

/** The common case: a component that only needs to turn keys into sentences. */
export function useT(): TFunction {
  return useI18n().t;
}
