/**
 * The update banner through every phase the updater reports: what it says, which buttons it
 * offers, and what each button asks the backend for.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UpdateState } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";
import { ConfirmProvider } from "@/shared/ui/ConfirmProvider";

import UpdateBanner, { type UpdateBannerProps } from "./UpdateBanner";

const REPO = "https://github.com/problem-xyz/aion2-map-overlay";

function en(key: string, params: Record<string, string> = {}): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return Object.entries(params).reduce((m, [k, v]) => m.replace(`{${k}}`, v), message);
}

function mount(update: UpdateState | undefined, props: Partial<UpdateBannerProps> = {}) {
  const all: UpdateBannerProps = {
    update,
    repoUrl: REPO,
    editorOpen: false,
    onDownload: vi.fn(),
    onRestart: vi.fn(),
    onSkip: vi.fn(),
    onOpenUrl: vi.fn(),
    ...props,
  };
  const view = render(
    <I18nProvider initial="en">
      <ConfirmProvider>
        <UpdateBanner {...all} />
      </ConfirmProvider>
    </I18nProvider>,
  );
  return { ...all, view };
}

afterEach(() => vi.restoreAllMocks());

describe("UpdateBanner", () => {
  it.each<UpdateState | undefined>([
    undefined,
    { phase: "disabled" },
    { phase: "idle" },
    { phase: "checking" },
    { phase: "none" },
    { phase: "failed", code: "update.failed", reason: "offline", stage: "check" },
  ])("shows nothing for %o", (update) => {
    const { view } = mount(update);
    expect(view.container.innerHTML).toBe("");
  });

  it("offers a found version for download, with its release notes", () => {
    const p = mount({ phase: "available", version: "1.2.0", skipped: false });

    expect(screen.getByRole("status").textContent).toContain(
      en("panel.update.available", { version: "1.2.0" }),
    );
    fireEvent.click(screen.getByRole("button", { name: en("panel.update.download") }));
    expect(p.onDownload).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: en("panel.update.releaseNotes") }));
    expect(p.onOpenUrl).toHaveBeenCalledWith(`${REPO}/releases/tag/v1.2.0`);
  });

  it("shows a download as a progress bar, with no buttons to press meanwhile", () => {
    mount({ phase: "downloading", version: "1.2.0", progress: 40 });

    const bar = screen.getByRole("progressbar", { name: en("panel.update.progressLabel") });
    expect((bar as HTMLProgressElement).value).toBe(40);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("restarts into a ready version at once when the editor is closed", () => {
    const p = mount({ phase: "ready", version: "1.2.0", skipped: false });

    expect(screen.getByRole("status").textContent).toContain(
      en("panel.update.ready", { version: "1.2.0" }),
    );
    fireEvent.click(screen.getByRole("button", { name: en("panel.update.restartNow") }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(p.onRestart).toHaveBeenCalledTimes(1);
  });

  it("asks before a restart would drop unsaved work in an open editor", async () => {
    const p = mount({ phase: "ready", version: "1.2.0" }, { editorOpen: true });
    const restart = () =>
      fireEvent.click(screen.getByRole("button", { name: en("panel.update.restartNow") }));

    restart();
    screen.getByRole("alertdialog", { name: en("panel.update.confirmRestartEditor") });
    fireEvent.click(screen.getByRole("button", { name: en("common.dialog.cancel") }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(p.onRestart).not.toHaveBeenCalled();

    restart();
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: en("panel.update.restartNow") }));
    await waitFor(() => expect(p.onRestart).toHaveBeenCalledTimes(1));
  });

  it("skips a version through the backend", () => {
    const p = mount({ phase: "ready", version: "1.2.0" });
    fireEvent.click(screen.getByRole("button", { name: en("panel.update.skip") }));
    expect(p.onSkip).toHaveBeenCalledWith("1.2.0");
  });

  it("hides a version the user put off, and nothing else", () => {
    const p = mount({ phase: "ready", version: "1.2.0" });
    fireEvent.click(screen.getByRole("button", { name: en("panel.update.later") }));

    expect(p.view.container.innerHTML).toBe("");
    expect(p.onSkip).not.toHaveBeenCalled();
    expect(p.onRestart).not.toHaveBeenCalled();

    p.view.rerender(
      <I18nProvider initial="en">
        <ConfirmProvider>
          <UpdateBanner {...p} update={{ phase: "available", version: "1.3.0" }} />
        </ConfirmProvider>
      </I18nProvider>,
    );
    expect(screen.getByRole("status").textContent).toContain("1.3.0");
  });

  it("stays away for a skipped version", () => {
    const { view } = mount({ phase: "ready", version: "1.2.0", skipped: true });
    expect(view.container.innerHTML).toBe("");
  });

  it("has no release notes link without the repository address (an older backend)", () => {
    mount({ phase: "available", version: "1.2.0" }, { repoUrl: undefined });
    expect(screen.queryByRole("button", { name: en("panel.update.releaseNotes") })).toBeNull();
  });
});
