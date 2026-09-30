/**
 * The support tiles and the crypto dialog behind one of them: what each tile opens, and that
 * the dialog shows and copies the address of the coin that is picked.
 */

import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SupportLinks } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";

import { WALLETS } from "../wallets";

import SupportBlock, { type SupportBlockProps } from "./SupportBlock";

const REPO = "https://github.com/problem-xyz/aion2-map-overlay";
const LINKS: SupportLinks = {
  donate: "https://buymeacoffee.com/problem_xyz",
  discord: "https://discord.gg/DV2SNF6PMh",
  partnerDiscord: "https://discord.gg/aion2global",
};

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(props: Partial<SupportBlockProps> = {}) {
  const all: SupportBlockProps = {
    links: LINKS,
    repoUrl: REPO,
    onOpenUrl: vi.fn(),
    onCopy: vi.fn(),
    ...props,
  };
  render(
    <I18nProvider initial="en">
      <SupportBlock {...all} />
    </I18nProvider>,
  );
  return all;
}

function tile(key: string) {
  return screen.getByRole("button", { name: new RegExp(en(key)) });
}

afterEach(() => vi.useRealTimers());

describe("SupportBlock", () => {
  it.each([
    ["panel.support.coffee", LINKS.donate],
    ["panel.support.discord", LINKS.discord],
    ["panel.support.partner", LINKS.partnerDiscord],
    ["panel.support.github", REPO],
  ])("%s opens its page", (key, url) => {
    const p = mount();
    fireEvent.click(tile(key));
    expect(p.onOpenUrl).toHaveBeenCalledWith(url);
  });

  it("leaves out the partner tile for a backend before api 20", () => {
    mount({ links: { donate: LINKS.donate, discord: LINKS.discord } });
    expect(
      screen.queryByRole("button", { name: new RegExp(en("panel.support.partner")) }),
    ).toBeNull();
  });

  it("leaves out the tiles whose address the backend did not send", () => {
    mount({ links: undefined, repoUrl: undefined });
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(tile("panel.support.crypto")).toBeTruthy();
  });

  it("opens the wallets on the first coin, and switches coin by click and by arrow", () => {
    mount();
    fireEvent.click(tile("panel.support.crypto"));
    const dialog = screen.getByRole("dialog", { name: en("panel.support.crypto") });
    const [first, second, , last] = WALLETS;
    expect(within(dialog).getByText(first!.network)).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("radio", { name: second!.ticker }));
    expect(within(dialog).getByRole("radio", { name: second!.ticker }).ariaChecked).toBe("true");
    expect(dialog.querySelector(".pn-crypto-address")?.textContent).toBe(second!.address);

    fireEvent.keyDown(within(dialog).getByRole("radio", { name: second!.ticker }), {
      key: "ArrowLeft",
    });
    fireEvent.keyDown(within(dialog).getByRole("radio", { name: first!.ticker }), {
      key: "ArrowLeft",
    });
    expect(dialog.querySelector(".pn-crypto-address")?.textContent).toBe(last!.address);
  });

  it("copies the address shown, says so for a moment, and closes on Escape", () => {
    vi.useFakeTimers();
    const p = mount();
    fireEvent.click(tile("panel.support.crypto"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: en("panel.support.copy") }));
    expect(p.onCopy).toHaveBeenCalledWith(WALLETS[0]!.address);
    expect(within(dialog).getByRole("button", { name: en("panel.support.copied") })).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(within(dialog).getByRole("button", { name: en("panel.support.copy") })).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("WALLETS", () => {
  // The checksums were checked when the addresses were added; this catches an edit that breaks
  // an address's shape, a character lost or doubled in a paste.
  const SHAPE: Record<string, RegExp> = {
    eth: /^0x[0-9a-fA-F]{40}$/,
    btc: /^bc1q[02-9ac-hj-np-z]{38}$/,
    sol: /^[1-9A-HJ-NP-Za-km-z]{43,44}$/,
    trx: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  };

  it.each(WALLETS.map((w) => [w.id, w.address]))("%s has the shape of its network", (id, a) => {
    expect(a).toMatch(SHAPE[id]!);
  });
});

describe("SupportBlock banner", () => {
  const BANNER = { image: "file:///banner.webp", url: "https://example.com/ad", label: "Guild" };

  it("opens the banner's page, and names it by what it advertises", () => {
    const p = mount({ banner: BANNER });

    const banner = screen.getByRole("button", { name: /Guild/ });
    expect(banner.textContent).toContain(en("panel.support.ad"));
    fireEvent.click(banner);

    expect(p.onOpenUrl).toHaveBeenCalledWith(BANNER.url);
  });

  it("sits between the donations and the links", () => {
    mount({ banner: BANNER });

    const order = [...document.querySelectorAll(".pn-support > *")].map((el) => el.className);
    expect(order).toEqual(["pn-support-group", "pn-banner", "pn-support-group"]);
  });

  it("is left out when the app ships none", () => {
    mount({ banner: null });
    expect(document.querySelector(".pn-banner")).toBeNull();
  });
});
