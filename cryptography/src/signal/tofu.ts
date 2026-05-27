export interface TrustedIdentity {
  userId: string;
  deviceId: number;
  identityKey: Buffer;
  firstSeenAt: string;
}

export type TofuVerifyResult =
  | { status: "trusted" }
  | { status: "first_use"; record: TrustedIdentity }
  | { status: "key_changed"; stored: Buffer; received: Buffer };

export function verifyIdentityTofu(
  store: Map<string, TrustedIdentity>,
  userId: string,
  deviceId: number,
  receivedIdentityKey: Buffer
): TofuVerifyResult {
  const key = `${userId}:${deviceId}`;
  const existing = store.get(key);

  if (!existing) {
    return {
      status: "first_use",
      record: {
        userId,
        deviceId,
        identityKey: Buffer.from(receivedIdentityKey),
        firstSeenAt: new Date().toISOString(),
      },
    };
  }

  if (existing.identityKey.equals(receivedIdentityKey)) {
    return { status: "trusted" };
  }

  return {
    status: "key_changed",
    stored: existing.identityKey,
    received: receivedIdentityKey,
  };
}

export function pinIdentity(store: Map<string, TrustedIdentity>, record: TrustedIdentity): void {
  store.set(`${record.userId}:${record.deviceId}`, record);
}
