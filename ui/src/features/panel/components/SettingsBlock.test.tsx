/**
 * The Settings block: that its sliders take their ranges from the schema Python sends, that the
 * algorithm settings sit behind a collapsed Advanced section, and that Reset asks first.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Settings, SettingsSchema } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";
import { ConfirmProvider } from "@/shared/ui/ConfirmProvider";

import SettingsBlock from "./SettingsBlock";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

const SETTINGS = {
  language: "auto",
  opacity: 0.85,
  fps: 60,
  tracking: "flow",
  detect_interval: 0.4,
  smoothing: 0.5,
  detector: "sift",
  transform: "similarity",
  detect_scale: 1,
  min_inliers: 20,
  route_view: "steps",
  route_ahead: 3,
  route_past: 3,
} as Settings;

// Deliberately not the ranges the panel used to hard-code, so a slider that still carried its
// own min and max would fail here.
const SCHEMA: SettingsSchema = {
  opacity: { type: "float", default: 0.85, min: 0.2, max: 0.9 },
  fps: { type: "int", default: 60, min: 45, max: 144 },
  detect_interval: { type: "float", default: 0.4, min: 0.2, max: 3 },
  smoothing: { type: "float", default: 0.5, min: 0, max: 0.8 },
  min_inliers: { type: "int", default: 20, min: 10, max: 50 },
  route_ahead: { type: "int", default: 3, min: 1, max: 10 },
  route_past: { type: "int", default: 3, min: 0, max: 10 },
};

// null for "no schema at all": undefined would pick up the default instead.
function mount(schema: SettingsSchema | null = SCHEMA, settings: Settings = SETTINGS) {
  const onReset = vi.fn();
  const onChange = vi.fn();
  render(
    <I18nProvider initial="en">
      <ConfirmProvider>
        <SettingsBlock
          settings={settings}
          schema={schema ?? undefined}
          onChange={onChange}
          onReset={onReset}
        />
      </ConfirmProvider>
    </I18nProvider>,
  );
  return { onReset, onChange };
}

function slider(labelKey: string): HTMLInputElement {
  return screen.getByRole("slider", { name: en(labelKey) });
}

describe("SettingsBlock", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("takes every slider's range from the schema", () => {
    mount();

    expect(slider("panel.settings.opacity")).toMatchObject({ min: "0.2", max: "0.9" });
    expect(slider("panel.settings.fps")).toMatchObject({ min: "45", max: "144", step: "5" });
    expect(slider("panel.settings.detectInterval")).toMatchObject({ min: "0.2", max: "3" });
    expect(slider("panel.settings.smoothing")).toMatchObject({ min: "0", max: "0.8" });
    expect(slider("panel.settings.minInliers")).toMatchObject({ min: "10", max: "50" });
  });

  it.each([
    ["steps", true, true],
    ["dim", true, true],
    ["all", false, true],
  ] as const)(
    "offers, for the route drawn as %s, only the step counts that change it",
    (view, ahead, past) => {
      mount(SCHEMA, { ...SETTINGS, route_view: view });

      const has = (key: string) => screen.queryByRole("slider", { name: en(key) }) !== null;
      expect(has("panel.settings.routeAhead")).toBe(ahead);
      expect(has("panel.settings.routePast")).toBe(past);
    },
  );

  it("says what no steps passed means rather than showing a zero", () => {
    mount(SCHEMA, { ...SETTINGS, route_past: 0 });

    expect(slider("panel.settings.routePast").getAttribute("aria-valuetext")).toBe(
      en("panel.settings.routePastNone"),
    );
  });

  it("leaves out a slider the schema gives no range for", () => {
    mount({ ...SCHEMA, fps: { type: "int", default: 60 } });

    expect(screen.queryByRole("slider", { name: en("panel.settings.fps") })).toBeNull();
    expect(slider("panel.settings.opacity")).toBeDefined();
  });

  it("offers no slider at all to a backend that sends no schema", () => {
    mount(null);

    expect(screen.queryAllByRole("slider")).toHaveLength(0);
    // the choices do not depend on a range, so they stay
    expect(screen.getByRole("radiogroup", { name: en("panel.settings.language") })).toBeDefined();
  });

  it("keeps the algorithm settings in an Advanced section that starts closed", async () => {
    const user = userEvent.setup();
    mount();

    const summary = screen.getByText(en("panel.settings.advanced"));
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    for (const key of [
      "panel.settings.detectInterval",
      "panel.settings.smoothing",
      "panel.settings.minInliers",
    ]) {
      expect(details?.contains(slider(key))).toBe(true);
    }
    for (const key of ["panel.settings.opacity", "panel.settings.fps"]) {
      expect(details?.contains(slider(key))).toBe(false);
    }

    await user.click(summary);

    expect(details?.open).toBe(true);
  });

  it("asks before resetting, and does nothing when the answer is no", async () => {
    const user = userEvent.setup();
    const { onReset } = mount();

    await user.click(screen.getByRole("button", { name: en("panel.settings.reset") }));

    screen.getByRole("alertdialog", { name: en("panel.settings.confirmReset") });
    await user.click(screen.getByRole("button", { name: en("common.dialog.cancel") }));
    expect(onReset).not.toHaveBeenCalled();
  });

  it("resets once the user confirms", async () => {
    const user = userEvent.setup();
    const { onReset, onChange } = mount();

    await user.click(screen.getByRole("button", { name: en("panel.settings.reset") }));
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: en("panel.settings.reset") }));

    expect(onReset).toHaveBeenCalledTimes(1);
    expect(onChange).not.toHaveBeenCalled(); // the reset is one call, not a patch per field
  });
});
