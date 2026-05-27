const B64 = "base64";

export function toBase64(buf: Buffer): string {
  return buf.toString(B64);
}

export function fromBase64(encoded: string): Buffer {
  return Buffer.from(encoded, B64);
}

export function assertKeyLength(buf: Buffer, bytes: number, label: string): void {
  if (buf.length !== bytes) {
    throw new Error(`${label} must be ${bytes} bytes, got ${buf.length}`);
  }
}
