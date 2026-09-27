/**
 * The project's crypto wallets, as the crypto donation dialog lists them.
 *
 * Each address was checked against its network's own checksum when it was added (EIP-55,
 * bech32, base58check, a 32-byte key): one wrong character sends a donation nowhere, and no
 * wallet would warn.
 */

export type CoinId = "eth" | "btc" | "sol" | "trx";

export interface Wallet {
  id: CoinId;
  ticker: string;
  /** The network's own name, which no language translates. */
  network: string;
  address: string;
}

export const WALLETS: readonly Wallet[] = [
  {
    id: "eth",
    ticker: "ETH",
    network: "Ethereum",
    address: "0x2030bEE0F82a7c3eb00d5391dDD63C49d99435Ff",
  },
  {
    id: "btc",
    ticker: "BTC",
    network: "Bitcoin",
    address: "bc1qxwfddau6a9dgmmels4nd82mdjzvmt05w02mkhf",
  },
  {
    id: "sol",
    ticker: "SOL",
    network: "Solana",
    address: "7P3M14B9RBAUdbj1KZ4m9Ab53ko3VnBAJFkwFexsEmv2",
  },
  {
    id: "trx",
    ticker: "TRX",
    network: "TRON",
    address: "TEReugvvEFwP9qJ5eCwWasb9m7n2jpAoCi",
  },
];
