/**
 * A question with more than one answer: the editor's close offers "Close without saving" and
 * "Save and close", and each must come back as itself.
 */

import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/shared/i18n";
import { ConfirmProvider, type Choice } from "@/shared/ui/ConfirmProvider";

import { useAsk } from "./useAsk";

const CHOICES: Choice<"discard" | "save">[] = [
  { id: "discard", label: "Close without saving", tone: "danger" },
  { id: "save", label: "Save and close", tone: "primary" },
];

function wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider initial="en">
      <ConfirmProvider>{children}</ConfirmProvider>
    </I18nProvider>
  );
}

function ask() {
  const { result } = renderHook(() => useAsk(), { wrapper });
  let answer!: Promise<"discard" | "save" | null>;
  act(() => {
    answer = result.current("The route has unsaved changes.", CHOICES);
  });
  return answer;
}

describe("useAsk", () => {
  it("offers the cancelling cross first, then the answers in the order given", () => {
    void ask();

    const names = screen
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label") ?? b.textContent);
    expect(names).toEqual(["Cancel", "Close without saving", "Save and close"]);
  });

  it.each(["discard", "save"] as const)("resolves %s with its own id", async (id) => {
    const answer = ask();
    const label = CHOICES.find((c) => c.id === id)?.label ?? "";

    await userEvent.click(screen.getByRole("button", { name: label }));

    await expect(answer).resolves.toBe(id);
  });

  it("resolves null on Cancel", async () => {
    const answer = ask();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await expect(answer).resolves.toBeNull();
  });

  it("goes round all three buttons with Tab", async () => {
    void ask();
    const [cancel, discard, save] = screen.getAllByRole("button");

    await userEvent.tab();
    expect(document.activeElement).toBe(discard);
    await userEvent.tab();
    expect(document.activeElement).toBe(save);
    await userEvent.tab();
    expect(document.activeElement).toBe(cancel);
  });
});
