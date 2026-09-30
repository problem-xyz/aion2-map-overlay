import { useState, type ReactNode } from "react";

import type { SupportLinks } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";

import { WALLETS } from "../wallets";

import BrandMark from "./BrandMark";
import CryptoDialog from "./CryptoDialog";

export interface SupportBlockProps {
  /** getState's links; without them (a backend before api 19) the two tiles they open are left out. */
  links: SupportLinks | undefined;
  repoUrl: string | undefined;
  onOpenUrl: (url: string) => void;
  onCopy: (text: string) => void;
}

interface TileProps {
  mark: ReactNode;
  label: string;
  hint: string;
  /** Opens a page in the browser, which the arrow in the corner says. */
  external?: boolean;
  onClick: () => void;
}

function Tile({ mark, label, hint, external = false, onClick }: TileProps) {
  return (
    <button type="button" className="pn-support-tile" onClick={onClick}>
      <span className="pn-support-mark">{mark}</span>
      <span className="pn-support-text">
        <span className="pn-support-label">{label}</span>
        <span className="pn-support-hint">{hint}</span>
      </span>
      {external ? <Icon name="external" className="pn-support-out" /> : null}
    </button>
  );
}

/**
 * Under every section: the two ways to donate on a warm row of their own, the Discord server
 * and the releases on a plain one below. Crypto opens a dialog of wallets rather than a page.
 */
export default function SupportBlock({ links, repoUrl, onOpenUrl, onCopy }: SupportBlockProps) {
  const t = useT();
  const [cryptoOpen, setCryptoOpen] = useState(false);

  return (
    <section className="pn-support" aria-label={t("panel.support.title")}>
      <div className="pn-support-row give">
        {links ? (
          <Tile
            mark={<BrandMark brand="coffee" />}
            label={t("panel.support.coffee")}
            hint={t("panel.support.coffeeHint")}
            external
            onClick={() => onOpenUrl(links.donate)}
          />
        ) : null}
        <Tile
          mark={
            <span className="pn-support-coins">
              {WALLETS.map((w) => (
                <BrandMark key={w.id} brand={w.id} />
              ))}
            </span>
          }
          label={t("panel.support.crypto")}
          hint={WALLETS.map((w) => w.ticker).join(" · ")}
          onClick={() => setCryptoOpen(true)}
        />
      </div>
      <div className="pn-support-row">
        {links ? (
          <Tile
            mark={<BrandMark brand="discord" />}
            label={t("panel.support.discord")}
            hint={t("panel.support.discordHint")}
            external
            onClick={() => onOpenUrl(links.discord)}
          />
        ) : null}
        {links?.partnerDiscord ? (
          <Tile
            mark={<BrandMark brand="discord" />}
            label={t("panel.support.partner")}
            hint={t("panel.support.partnerHint")}
            external
            onClick={() => onOpenUrl(links.partnerDiscord ?? "")}
          />
        ) : null}
        {repoUrl ? (
          <Tile
            mark={<BrandMark brand="github" />}
            label={t("panel.support.github")}
            hint={t("panel.support.githubHint")}
            external
            onClick={() => onOpenUrl(repoUrl)}
          />
        ) : null}
      </div>
      {cryptoOpen ? <CryptoDialog onCopy={onCopy} onClose={() => setCryptoOpen(false)} /> : null}
    </section>
  );
}
