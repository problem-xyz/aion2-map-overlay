import { useMemo } from "react";
import { encode, QrCodeDataType } from "uqr";

import type { CoinId } from "../wallets";

import BrandMark from "./BrandMark";

// The finder squares' corners, in modules from the code's own
const FINDERS = [
  [0, 0],
  [1, 0],
  [0, 1],
] as const;
// Quiet space round the code, in modules: scanners want four, the white plate gives two more
const MARGIN = 2;

/**
 * An address as a QR code, drawn in dots with rounded finders and the coin's badge in the
 * middle.
 *
 * The badge covers a square of about a quarter of the code's width, some 7% of its modules:
 * the highest correction level restores up to 30%, so every phone reads it all the same.
 */
export default function QrCode({
  value,
  coin,
  label,
}: {
  value: string;
  coin: CoinId;
  label: string;
}) {
  const { size, dots, hole } = useMemo(() => {
    const qr = encode(value, { ecc: "H", border: 0 });
    const n = qr.size;
    // An odd side keeps the hole centred on a module, as the code itself is
    const side = Math.round(n * 0.26) | 1;
    const lo = (n - side) / 2;
    const hi = lo + side;
    let path = "";
    qr.data.forEach((row, y) =>
      row.forEach((dark, x) => {
        const inHole = x >= lo && x < hi && y >= lo && y < hi;
        if (!dark || inHole || qr.types[y]?.[x] === QrCodeDataType.Position) return;
        path += `M${x + 0.5} ${y + 0.08}a.42.42 0 1 0 .001 0z`;
      }),
    );
    return { size: n, dots: path, hole: { at: lo, side } };
  }, [value]);

  const box = size + MARGIN * 2;
  const logo = hole.side - 1;
  return (
    <svg
      className="pn-qr"
      viewBox={`${-MARGIN} ${-MARGIN} ${box} ${box}`}
      role="img"
      aria-label={label}
    >
      <rect x={-MARGIN} y={-MARGIN} width={box} height={box} rx="2.4" className="pn-qr-plate" />
      <path d={dots} className="pn-qr-ink" />
      {FINDERS.map(([fx, fy]) => {
        const x = fx * (size - 7);
        const y = fy * (size - 7);
        return (
          <g key={`${fx}${fy}`} className="pn-qr-ink">
            <path
              fillRule="evenodd"
              d={`M${x + 2} ${y}h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2z
                  M${x + 2.2} ${y + 1}h2.6a1.2 1.2 0 0 1 1.2 1.2v2.6a1.2 1.2 0 0 1-1.2 1.2h-2.6a1.2 1.2 0 0 1-1.2-1.2v-2.6a1.2 1.2 0 0 1 1.2-1.2z`}
            />
            <rect x={x + 2} y={y + 2} width="3" height="3" rx="0.9" />
          </g>
        );
      })}
      <g
        transform={`translate(${hole.at + 0.5} ${hole.at + 0.5}) scale(${logo / 32})`}
        className="pn-qr-logo"
      >
        <BrandMark brand={coin} />
      </g>
    </svg>
  );
}
