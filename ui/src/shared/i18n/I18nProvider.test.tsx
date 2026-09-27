/**
 * What I18nProvider pins: the wording a consumer sees follows setLanguage, `auto` is resolved
 * from the browser before Python has said anything, a key nothing carries renders as itself
 * rather than as a gap, and the chosen language reaches document.documentElement where the
 * browser's hyphenation and a screen reader can find it.
 *
 * Russian sentences are compared against the shipped catalogue instead of being written out: the
 * language gate keeps Cyrillic out of a .tsx file, and a literal here would drift from ru.json.
 *
 * This file also carries the test for keys.ts, which has no runtime surface of its own: the
 * `@ts-expect-error` below fails `tsc --noEmit` the moment MessageKey stops rejecting a typo.
 */

import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import { type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogs } from "./catalogs";
import { I18nProvider, useI18n, useT } from "./I18nProvider";

const KEY = "common.connecting";

function sentence(locale: string): string {
  const message = catalogs.get(locale)?.get(KEY);
  if (typeof message !== "string") throw new Error(`${locale} has no string for ${KEY}`);
  return message;
}

function text(testId: string): string | null {
  return screen.getByTestId(testId).textContent;
}

function Probe() {
  const { locale, available, format, setLanguage } = useI18n();
  const t = useT();
  return (
    <div>
      <output data-testid="locale">{locale}</output>
      <output data-testid="sentence">{t(KEY)}</output>
      <output data-testid="number">{format.number(1234.5)}</output>
      <output data-testid="available">{available.join(" ")}</output>
      <button type="button" onClick={() => setLanguage("ru")}>
        to-ru
      </button>
      <button type="button" onClick={() => setLanguage("en")}>
        to-en
      </button>
      <button type="button" onClick={() => setLanguage("de")}>
        to-de
      </button>
    </div>
  );
}

function wrapperFor(initial: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <I18nProvider initial={initial}>{children}</I18nProvider>;
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("the catalogues this suite compares against", () => {
  it("say something different in each language", () => {
    expect(sentence("ru")).not.toBe(sentence("en"));
  });
});

describe("I18nProvider", () => {
  it("speaks the language it was handed", () => {
    render(
      <I18nProvider initial="ru">
        <Probe />
      </I18nProvider>,
    );
    expect(text("locale")).toBe("ru");
    expect(text("sentence")).toBe(sentence("ru"));
  });

  it("re-renders consumers in the new wording when the language is switched", () => {
    render(
      <I18nProvider initial="en">
        <Probe />
      </I18nProvider>,
    );
    expect(text("sentence")).toBe(sentence("en"));

    fireEvent.click(screen.getByText("to-ru"));
    expect(text("locale")).toBe("ru");
    expect(text("sentence")).toBe(sentence("ru"));

    fireEvent.click(screen.getByText("to-en"));
    expect(text("locale")).toBe("en");
    expect(text("sentence")).toBe(sentence("en"));
  });

  it("re-formats numbers in the new language too", () => {
    render(
      <I18nProvider initial="en">
        <Probe />
      </I18nProvider>,
    );
    expect(text("number")).toBe("1,234.5");

    fireEvent.click(screen.getByText("to-ru"));
    expect(text("number")).not.toBe("1,234.5");
  });

  it("takes a setting, not a locale: `auto` is resolved from the browser", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("ru-RU");
    render(
      <I18nProvider initial="auto">
        <Probe />
      </I18nProvider>,
    );
    expect(text("locale")).toBe("ru");
  });

  it("lands on English when the browser speaks a language that never shipped", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
    render(
      <I18nProvider initial="auto">
        <Probe />
      </I18nProvider>,
    );
    expect(text("locale")).toBe("en");
  });

  it("lands on English when a language that never shipped is chosen", () => {
    render(
      <I18nProvider initial="en">
        <Probe />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByText("to-de"));
    expect(text("locale")).toBe("en");
    expect(text("sentence")).toBe(sentence("en"));
  });

  it("follows the initial setting when the host changes it", () => {
    // The steps plaque is told its language by Python and re-renders the provider with it.
    const { rerender } = render(
      <I18nProvider initial="en">
        <Probe />
      </I18nProvider>,
    );
    expect(text("locale")).toBe("en");

    rerender(
      <I18nProvider initial="ru">
        <Probe />
      </I18nProvider>,
    );
    expect(text("locale")).toBe("ru");
    expect(text("sentence")).toBe(sentence("ru"));
  });

  it("puts the language on the document element", () => {
    render(
      <I18nProvider initial="ru">
        <Probe />
      </I18nProvider>,
    );
    expect(document.documentElement.lang).toBe("ru");

    fireEvent.click(screen.getByText("to-en"));
    expect(document.documentElement.lang).toBe("en");
  });

  it("exposes the languages that shipped", () => {
    render(
      <I18nProvider initial="en">
        <Probe />
      </I18nProvider>,
    );
    expect(text("available")).toBe([...catalogs.keys()].sort().join(" "));
  });
});

describe("a key no catalogue carries", () => {
  it("renders as the key itself rather than as a gap", () => {
    const { result } = renderHook(() => useI18n(), { wrapper: wrapperFor("ru") });
    expect(result.current.t("panel.nothing.at.all" as never)).toBe("panel.nothing.at.all");
  });

  it("is reported once, not once per render", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { result } = renderHook(() => useI18n(), { wrapper: wrapperFor("en") });
    // A key of this test's own: the set of keys already warned about is module state that
    // outlives the test, so a shared one would make this pass or fail on suite order.
    result.current.t("panel.reported.once" as never);
    result.current.t("panel.reported.once" as never);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("panel.reported.once"));
  });

  it("is reported by a built UI too, where the console is the app log", () => {
    // A shipped build is the one that meets a key nobody tested, and Python's LoggingPage is
    // the only thing that reads its console. Gating the warning on DEV left the log silent.
    vi.stubEnv("DEV", false);
    vi.stubEnv("PROD", true);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { result } = renderHook(() => useI18n(), { wrapper: wrapperFor("en") });

    result.current.t("panel.reported.in.a.build" as never);

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("panel.reported.in.a.build"));
  });

  it("is a compile error when it is a typo, which is all keys.ts does", () => {
    const { result } = renderHook(() => useI18n(), { wrapper: wrapperFor("en") });
    expect(result.current.t(KEY)).toBe(sentence("en"));
    // @ts-expect-error `common.connectin` is not a key of locales/en.json, so MessageKey rejects it
    expect(result.current.t("common.connectin")).toBe("common.connectin");
  });
});

describe("useI18n", () => {
  it("refuses to work outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useI18n())).toThrow(/outside I18nProvider/);
  });
});
