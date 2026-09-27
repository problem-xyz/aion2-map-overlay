/**
 * Pins the dialog's answers: callers branch on the resolved boolean to decide whether a
 * destructive edit happens, so anything but the confirming button must resolve `false`. The
 * identity is stable because the function is a dependency of memoised handlers.
 */

import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/shared/i18n";
import { ConfirmProvider } from "@/shared/ui/ConfirmProvider";

import { useConfirm, type Confirm } from "./useConfirm";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider initial="en">
      <ConfirmProvider>{children}</ConfirmProvider>
    </I18nProvider>
  );
}

function setup() {
  const { result, rerender } = renderHook(() => useConfirm(), { wrapper });
  const ask = (...args: Parameters<Confirm>) => {
    let answer!: Promise<boolean>;
    act(() => {
      answer = result.current(...args);
    });
    return answer;
  };
  return { result, rerender, ask };
}

describe("useConfirm", () => {
  it("shows the message in a modal dialog", () => {
    const { ask } = setup();
    void ask("Delete the route?");

    const dialog = screen.getByRole("alertdialog", { name: "Delete the route?" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("resolves true on the confirming button", async () => {
    const { ask } = setup();
    const answer = ask("Delete the route?", { confirmLabel: "Delete route" });

    await userEvent.click(screen.getByRole("button", { name: "Delete route" }));

    await expect(answer).resolves.toBe(true);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("resolves false on Cancel", async () => {
    const { ask } = setup();
    const answer = ask("Delete the route?");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await expect(answer).resolves.toBe(false);
  });

  it("resolves false on Escape, and the key goes no further", async () => {
    const { ask } = setup();
    let reachedWindow = false;
    const onKey = () => (reachedWindow = true);
    window.addEventListener("keydown", onKey);
    const answer = ask("Delete the route?");

    await userEvent.keyboard("{Escape}");

    window.removeEventListener("keydown", onKey);
    await expect(answer).resolves.toBe(false);
    expect(reachedWindow).toBe(false);
  });

  it("resolves false on a click outside the card", async () => {
    const { ask } = setup();
    const answer = ask("Delete the route?");

    const card = screen.getByRole("alertdialog");
    act(() => {
      fireEvent.mouseDown(card.parentElement as HTMLElement);
    });

    await expect(answer).resolves.toBe(false);
  });

  it("starts on the cancelling cross, so Enter right away keeps the work", async () => {
    const { ask } = setup();
    const answer = ask("Delete the route?");

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.keyboard("{Enter}");

    await expect(answer).resolves.toBe(false);
  });

  it("makes the page behind it inert, and gives it back after", async () => {
    render(<button type="button">Behind</button>);
    const behind = screen.getByRole("button", { name: "Behind" });
    const host = behind.parentElement as HTMLElement;
    const { ask } = setup();
    const answer = ask("Delete the route?");

    expect(host.inert).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await answer;
    expect(host.inert).toBe(false);
  });

  it("shows two questions one after the other", async () => {
    const { ask } = setup();
    const first = ask("First?");
    const second = ask("Second?");

    expect(screen.getAllByRole("alertdialog")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "OK" }));
    await expect(first).resolves.toBe(true);

    screen.getByRole("alertdialog", { name: "Second?" });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await expect(second).resolves.toBe(false);
  });

  it("keeps the same identity across rerenders", () => {
    const { result, rerender } = setup();
    const first = result.current;

    rerender();
    rerender();

    expect(result.current).toBe(first);
  });
});
