/**
 * Server DB columns for the crypto layer.
 * Private keys (identity, pre-keys, ratchet state) stay on the client only.
 */

/** Login: store only the PHC string; salt is already inside it. */
export interface UserAuthRow {
  user_id: string;
  password_hash: string;
}

/**
 * Public key material uploaded at registration / pre-key refresh.
 * All *_b64 fields are standard base64 (not base64url).
 */
export interface DeviceKeysRow {
  user_id: string;
  device_id: number;
  registration_id: number;
  identity_key_public_b64: string;
  identity_signing_public_b64: string;
  signed_prekey_id: number;
  signed_prekey_public_b64: string;
  signed_prekey_signature_b64: string;
  signed_prekey_created_at: string;
}

/** One row per unused one-time pre-key. Delete or mark used after X3DH consumes it. */
export interface OneTimePreKeyRow {
  user_id: string;
  device_id: number;
  prekey_id: number;
  prekey_public_b64: string;
  used_at: string | null;
}

/**
 * Message relay: ciphertext only. Use wireFormat.serializeWireMessage for payload column.
 */
export interface MessageRow {
  message_id: string;
  sender_user_id: string;
  sender_device_id: number;
  recipient_user_id: string;
  recipient_device_id: number;
  wire_payload_json: string;
  created_at: string;
}

/** Optional metadata the server may index (not secret). */
export interface MessageMetadata {
  conversation_id: string;
  is_first_message: boolean;
  consumed_one_time_prekey_id: number | null;
}
