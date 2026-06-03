import { webcrypto } from "node:crypto";
import { setWebCrypto } from "@privacyresearch/libsignal-protocol-typescript";

let configured = false;

export function ensureSignalCrypto(): void {
  if (configured) return;
  setWebCrypto(webcrypto as globalThis.Crypto);
  configured = true;
}

ensureSignalCrypto();
