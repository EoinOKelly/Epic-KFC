import { webcrypto } from "node:crypto";
import { setWebCrypto } from "@privacyresearch/libsignal-protocol-typescript";

let configured = false;

/** Node 18+ Web Crypto for @privacyresearch/libsignal-protocol-typescript. */
export function ensureSignalCrypto(): void {
  if (configured) return;
  setWebCrypto(webcrypto as globalThis.Crypto);
  configured = true;
}

ensureSignalCrypto();
