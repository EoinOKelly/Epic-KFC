export { SIGNAL_PROTOCOL } from "./libsignalMessaging";
export {
  buildPreKeyBundle,
  decryptFromSender,
  encryptForRecipient,
  establishSession,
  identityKeyBytes,
  preKeyBundleFromDb,
  protocolAddress,
} from "./libsignalMessaging";
export type { LibSignalWireMessage } from "./libsignalMessaging";

export {
  deviceToDbRows,
  deviceKeyUploadPayloadFromRow,
  deviceToPublicBundle,
  generateDevice,
  preKeyBundleFromApiResponse,
  publicBundleFromDb,
} from "./libsignalDevice";
export type { ApiPreKeyBundleResponse, GeneratedDevice } from "./libsignalDevice";

export { InMemoryProtocolStore } from "./signalProtocolStore";

export { verifyIdentityTofu, pinIdentity } from "./tofu";
export type { TrustedIdentity, TofuVerifyResult } from "./tofu";

/** @deprecated Use encryptForRecipient */
export { encryptForRecipient as signalEncrypt } from "./libsignalMessaging";
/** @deprecated Use decryptFromSender */
export { decryptFromSender as signalDecrypt } from "./libsignalMessaging";
