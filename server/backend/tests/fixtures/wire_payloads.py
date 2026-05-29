"""Shared opaque wire payloads matching cryptography/ libsignal-v1 format."""

# Structural placeholders (valid base64, non-empty). Real ciphertext comes from the client.
WIRE_PAYLOAD = (
    '{"format":"libsignal-v1","type":3,"bodyB64":"b3JpZ2luYWw=",'
    '"registrationId":12345}'
)

NEW_WIRE_PAYLOAD = '{"format":"libsignal-v1","type":1,"bodyB64":"bmV3"}'

FORWARDED_WIRE_PAYLOAD = NEW_WIRE_PAYLOAD

ALT_WIRE_PAYLOAD = (
    '{"format":"libsignal-v1","type":1,"bodyB64":"YWx0ZXJuYXRl"}'
)
