import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { useT, type MessageKey } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import Modal from "@/shared/ui/Modal";

import { WALLETS, type CoinId } from "../wallets";

import BrandMark from "./BrandMark";
import QrCode from "./QrCode";

export const COPIED_MS = 1600;
// The characters a person compares after pasting, set brighter at both ends of the address
const EDGE = 6;
// What each address takes, spelt out so the catalogue check can see every key has a caller
const ACCEPTS: Record<CoinId, MessageKey> = {
  eth: "panel.support.accepts.eth",
  btc: "panel.support.accepts.btc",
  sol: "panel.support.accepts.sol",
  trx: "panel.support.accepts.trx",
};

interface CryptoDialogProps {
  onCopy: (address: string) => void;
  onClose: () => void;
}

/**
 * The wallets, one network at a time: a coin picked above, its QR code, the address and a copy
 * button under it. The line under the network's name says what the address takes, since a coin
 * sent over another network is lost.
 */
export default function CryptoDialog({ onCopy, onClose }: CryptoDialogProps) {
  const t = useT();
  const titleId = useId();
  const [coin, setCoin] = useState<CoinId>(WALLETS[0]!.id);
  const [copied, setCopied] = useState(false);
  const coins = useRef<(HTMLButtonElement | null)[]>([]);
  const wallet = WALLETS.find((w) => w.id === coin) ?? WALLETS[0]!;
  const at = WALLETS.indexOf(wallet);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const pick = (id: CoinId) => {
    setCoin(id);
    setCopied(false);
  };

  // A radio group: one tab stop, arrows between the coins, and the choice follows the focus
  const onCoinKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const to = (at + step + WALLETS.length) % WALLETS.length;
    coins.current[to]?.focus();
    pick(WALLETS[to]!.id);
  };

  const { address } = wallet;
  return (
    <Modal
      labelledBy={titleId}
      closeLabel={t("panel.support.close")}
      onClose={onClose}
      className="pn-crypto"
    >
      <h2 id={titleId} className="pn-crypto-title">
        {t("panel.support.crypto")}
      </h2>

      <div className="pn-crypto-coins" role="radiogroup" aria-label={t("panel.support.network")}>
        {WALLETS.map((w, i) => (
          <button
            key={w.id}
            ref={(node) => {
              coins.current[i] = node;
            }}
            type="button"
            role="radio"
            aria-checked={w.id === coin}
            tabIndex={w.id === coin ? 0 : -1}
            className="pn-crypto-coin"
            onClick={() => pick(w.id)}
            onKeyDown={onCoinKey}
          >
            <BrandMark brand={w.id} className="pn-crypto-coin-mark" />
            {w.ticker}
          </button>
        ))}
      </div>

      {/* Keyed by the coin, so a new pick draws in rather than swapping in place */}
      <div key={wallet.id} className="pn-crypto-card">
        <QrCode
          value={address}
          coin={wallet.id}
          label={t("panel.support.qr", { network: wallet.network })}
        />
        <p className="pn-crypto-network">
          <strong>{wallet.network}</strong>
          <span>{t(ACCEPTS[wallet.id])}</span>
        </p>
        <code className="pn-crypto-address">
          <b>{address.slice(0, EDGE)}</b>
          {address.slice(EDGE, -EDGE)}
          <b>{address.slice(-EDGE)}</b>
        </code>
        <button
          type="button"
          className={
            copied
              ? "ui-modal-btn ui-with-icon pn-crypto-copy done"
              : "ui-modal-btn ui-with-icon pn-crypto-copy"
          }
          onClick={() => {
            onCopy(address);
            setCopied(true);
          }}
        >
          <Icon name={copied ? "check" : "copy"} />
          {copied ? t("panel.support.copied") : t("panel.support.copy")}
        </button>
        <span className="ui-sr-only" role="status">
          {copied ? t("panel.support.copied") : ""}
        </span>
      </div>
    </Modal>
  );
}
