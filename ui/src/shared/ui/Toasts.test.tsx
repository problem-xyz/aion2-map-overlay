/**
 * Toasts is where a notify payload becomes a sentence. Two things are worth holding still: the
 * lookup happens while drawing, so switching language repaints a toast that is already up, and a
 * code this build has no message for still shows the English text Python sent.
 *
 * Expected sentences are read out of the catalogues rather than written here: a literal would
 * duplicate locales/*.json and put Cyrillic in a source file.
 */

import { act, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogs, I18nProvider, useI18n } from "../i18n";

import { ToastProvider, useToasts } from "./ToastProvider";
import Toasts, { EXIT_MS } from "./Toasts";

function message(locale: string, key: string): string {
  const value = catalogs.get(locale)?.get(key);
  if (typeof value !== "string") throw new Error(`no ${locale} message for ${key}`);
  return value;
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider initial="en">
      <ToastProvider>
        {children}
        <Toasts />
      </ToastProvider>
    </I18nProvider>
  );
}

function mount() {
  return renderHook(() => ({ queue: useToasts(), i18n: useI18n() }), { wrapper: Wrapper });
}

describe("Toasts", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("puts nothing in the document while the queue is empty", () => {
    mount();

    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    // Not even the empty container: it is position: fixed over the whole panel.
    expect(document.body.firstElementChild?.children).toHaveLength(0);
  });

  it("translates a code into the current language", () => {
    const view = mount();

    act(() => view.result.current.queue.push({ level: "info", code: "update.none" }));

    expect(screen.getByRole("status").textContent).toBe(message("en", "notify.update.none"));
  });

  it("repaints a toast already on screen when the language changes", () => {
    const view = mount();
    const english = message("en", "notify.update.none");
    const russian = message("ru", "notify.update.none");
    expect(russian).not.toBe(english);

    act(() => view.result.current.queue.push({ level: "info", code: "update.none" }));
    expect(screen.getByRole("status").textContent).toBe(english);

    act(() => view.result.current.i18n.setLanguage("ru"));

    expect(screen.getByRole("status").textContent).toBe(russian);
  });

  it("fills the payload's params into the sentence", () => {
    const view = mount();

    act(() =>
      view.result.current.queue.push({
        level: "info",
        code: "route.saved",
        params: { name: "Ashen" },
      }),
    );

    expect(screen.getByRole("status").textContent).toBe(
      message("en", "notify.route.saved").replace("{name}", "Ashen"),
    );
  });

  it("shows the English text Python sent when the code has no message here", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const view = mount();

    act(() =>
      view.result.current.queue.push({
        level: "info",
        code: "invented.by.a.newer.backend",
        text: "Already formatted upstream",
      }),
    );

    expect(screen.getByRole("status").textContent).toBe("Already formatted upstream");
  });

  it("shows the bare code when neither a message nor a text exists", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const view = mount();

    act(() => view.result.current.queue.push({ level: "info", code: "invented.without.any.text" }));

    expect(screen.getByRole("status").textContent).toBe("invented.without.any.text");
  });

  it("shows the text of a payload that carries no code at all", () => {
    const view = mount();

    act(() => view.result.current.queue.push({ level: "info", text: "From an older backend" }));

    expect(screen.getByRole("status").textContent).toBe("From an older backend");
  });

  it("interrupts a screen reader for an error and waits its turn for anything else", () => {
    const view = mount();

    act(() => {
      view.result.current.queue.push({ level: "error", text: "broke" });
      view.result.current.queue.push({ level: "warning", text: "careful" });
      view.result.current.queue.push({ level: "info", text: "done" });
    });

    const shouted = screen.getByRole("alert");
    expect(shouted.textContent).toBe("broke");
    expect(shouted.getAttribute("aria-live")).toBe("assertive");

    const polite = screen.getAllByRole("status");
    expect(polite.map((node) => node.textContent)).toEqual(["careful", "done"]);
    expect(polite.map((node) => node.getAttribute("aria-live"))).toEqual(["polite", "polite"]);
  });

  it("keeps a dismissed toast drawn for its fade, out of the tree, and then lets it go", () => {
    vi.useFakeTimers();
    try {
      const view = mount();
      act(() => view.result.current.queue.push({ level: "info", text: "saved" }));
      const id = view.result.current.queue.toasts[0]?.id ?? 0;

      act(() => view.result.current.queue.dismiss(id));
      // said once already: the fading copy is for the eye, not announced again
      expect(screen.queryByRole("status")).toBeNull();
      const fading = document.querySelector(".toast.leaving");
      expect(fading?.textContent).toBe("saved");
      expect(fading?.getAttribute("aria-hidden")).toBe("true");

      act(() => {
        vi.advanceTimersByTime(EXIT_MS);
      });
      expect(document.querySelector(".toast")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not move a toast that stays when an older one leaves", () => {
    const view = mount();
    act(() => {
      view.result.current.queue.push({ level: "info", text: "first" });
      view.result.current.queue.push({ level: "info", text: "second" });
    });
    const second = screen.getAllByRole("status")[1];
    const id = view.result.current.queue.toasts[0]?.id ?? 0;

    act(() => view.result.current.queue.dismiss(id));

    // the same node, still second: a re-inserted one would play its entrance again
    expect(document.querySelectorAll(".toast")[1]).toBe(second);
  });
});
