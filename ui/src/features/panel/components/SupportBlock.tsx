import { useEffect, useId, useState, type ReactNode } from "react";

import type { BannerInfo, SupportLinks } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";

import { WALLETS } from "../wallets";

import BrandMark from "./BrandMark";
import CryptoDialog, { COPIED_MS } from "./CryptoDialog";

export interface SupportBlockProps {
  /** getState's links; without them (a backend before api 19) the two tiles they open are left out. */
  links: SupportLinks | undefined;
  repoUrl: string | undefined;
  /** The advertising banner that ships with the app; without one, the slot offers itself. */
  banner?: BannerInfo | null;
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

/** The banner's discount code, copied at a click, which says so for a moment as the wallets do. */
function PromoCode({
  code,
  discount,
  onCopy,
}: {
  code: string;
  discount: string;
  onCopy: (text: string) => void;
}) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  return (
    <div className="pn-promo">
      <span className="pn-promo-text">
        {t("panel.support.promo", { discount })} <code className="pn-promo-code">{code}</code>
      </span>
      <button
        type="button"
        className="btn-small ghost ui-with-icon"
        onClick={() => {
          onCopy(code);
          setCopied(true);
        }}
      >
        <Icon name={copied ? "check" : "copy"} />
        {copied ? t("panel.support.copied") : t("panel.support.copyCode")}
      </button>
    </div>
  );
}

/**
 * Under every section: the two ways to donate, the banner, then the community links, each under
 * its own heading so that giving and following are not one pile. Crypto opens a dialog of
 * wallets rather than a page.
 */
export default function SupportBlock({
  links,
  repoUrl,
  banner = null,
  onOpenUrl,
  onCopy,
}: SupportBlockProps) {
  const t = useT();
  const [cryptoOpen, setCryptoOpen] = useState(false);
  const giveId = useId();
  const linksId = useId();

  return (
    <div className="pn-support">
      <section className="pn-support-group" aria-labelledby={giveId}>
        <h2 id={giveId} className="pn-subhead">
          {t("panel.support.title")}
        </h2>
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
      </section>

      {banner ? (
        <button
          type="button"
          className="pn-banner"
          title={banner.label}
          onClick={() => onOpenUrl(banner.url)}
        >
          <img src={banner.image} alt={banner.label} />
          <span className="pn-banner-ad">{t("panel.support.ad")}</span>
        </button>
      ) : links ? (
        // No banner ships yet: the slot offers itself, and a click is the way to ask about it
        <button
          type="button"
          className="pn-banner pn-banner-slot"
          onClick={() => onOpenUrl(links.discord)}
        >
          <span className="pn-banner-slot-title">{t("panel.support.adSlot")}</span>
          <span className="pn-banner-slot-hint">{t("panel.support.adSlotHint")}</span>
        </button>
      ) : null}
      {banner?.code && banner.discount ? (
        <PromoCode code={banner.code} discount={banner.discount} onCopy={onCopy} />
      ) : null}

      <section className="pn-support-group" aria-labelledby={linksId}>
        <h2 id={linksId} className="pn-subhead">
          {t("panel.support.links")}
        </h2>
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
      </section>
      {cryptoOpen ? <CryptoDialog onCopy={onCopy} onClose={() => setCryptoOpen(false)} /> : null}
    </div>
  );
}
