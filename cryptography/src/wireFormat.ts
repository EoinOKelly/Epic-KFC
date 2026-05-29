import { LibSignalWireMessage } from "./signal/libsignalMessaging";

export type { LibSignalWireMessage as SignalWireMessage } from "./signal/libsignalMessaging";

export function serializeWireMessage(msg: LibSignalWireMessage): string {
  return JSON.stringify(msg);
}

export function deserializeWireMessage(json: string): LibSignalWireMessage {
  const parsed = JSON.parse(json) as LibSignalWireMessage;
  if (parsed.format !== "libsignal-v1") {
    throw new Error("deserializeWireMessage: expected libsignal-v1 wire format");
  }
  return parsed;
}
