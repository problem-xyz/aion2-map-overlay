/**
 * Pins the two deliberate silences in this hook: a falsy title leaves the previous caption
 * standing instead of blanking the window, and unmounting does not restore anything -- the
 * editor window keeps the last title it was given until something sets another one.
 */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useDocumentTitle } from "./useDocumentTitle";

let original: string;

beforeEach(() => {
  original = document.title;
  document.title = "before";
});

afterEach(() => {
  document.title = original;
});

describe("useDocumentTitle", () => {
  it("sets the document title", () => {
    renderHook(() => useDocumentTitle("Route editor"));

    expect(document.title).toBe("Route editor");
  });

  it("follows the title when it changes", () => {
    const { rerender } = renderHook(({ title }) => useDocumentTitle(title), {
      initialProps: { title: "one" },
    });

    rerender({ title: "two" });

    expect(document.title).toBe("two");
  });

  it("leaves the title alone when it is null", () => {
    renderHook(() => useDocumentTitle(null));

    expect(document.title).toBe("before");
  });

  it("leaves the title alone when it is undefined", () => {
    renderHook(() => useDocumentTitle(undefined));

    expect(document.title).toBe("before");
  });

  it("leaves the title alone when it is empty", () => {
    renderHook(() => useDocumentTitle(""));

    expect(document.title).toBe("before");
  });

  it("keeps the last title it was given when the title goes empty", () => {
    const initialProps: { title: string | null } = { title: "one" };
    const { rerender } = renderHook(({ title }) => useDocumentTitle(title), { initialProps });

    rerender({ title: null });

    expect(document.title).toBe("one");
  });

  it("leaves the title in place after unmount", () => {
    const { unmount } = renderHook(() => useDocumentTitle("Route editor"));

    unmount();

    expect(document.title).toBe("Route editor");
  });
});
