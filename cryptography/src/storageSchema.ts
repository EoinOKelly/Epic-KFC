/**
 * Server DB columns for the crypto layer (libsignal public material only).
 */

export interface UserAuthRow {
  user_id: string;
  password_hash: string;
}

export interface DeviceKeysRow {
  user_id: string;
  device_id: number;
  registration_id: number;
  identity_key_public_b64: string;
  signed_prekey_id: number;
  signed_prekey_public_b64: string;
  signed_prekey_signature_b64: string;
  signed_prekey_created_at: string;
  /** Reserved for @signalapp/libsignal-client (PQXDH); null with classic X3DH port. */
  kyber_prekey_id?: number | null;
  kyber_prekey_public_b64?: string | null;
  kyber_prekey_signature_b64?: string | null;
}

/** Device row plus optional one-time pre-key for bundle reconstruction. */
export type StoredDeviceKeysRow = DeviceKeysRow & {
  one_time_prekey_id?: number | null;
  one_time_prekey_public_b64?: string | null;
};

export interface OneTimePreKeyRow {
  user_id: string;
  device_id: number;
  prekey_id: number;
  prekey_public_b64: string;
  used_at: string | null;
}

export interface MessageRow {
  message_id: string;
  sender_user_id: string;
  sender_device_id: number;
  recipient_user_id: string;
  recipient_device_id: number;
  wire_payload_json: string;
  created_at: string;
}

export interface MessageMetadata {
  conversation_id: string;
  is_prekey_message: boolean;
}
