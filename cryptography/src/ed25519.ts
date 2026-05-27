import * as crypto from "node:crypto";
import { assertKeyLength } from "./bufferUtils";

export interface Ed25519KeyPair {
  publicKey: Buffer;
  privateKey: Buffer;
}

export function generateEd25519KeyPair(): Ed25519KeyPair {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const privJwk = privateKey.export({ format: "jwk" }) as { d?: string };
  const pubJwk = publicKey.export({ format: "jwk" }) as { x?: string };
  if (!privJwk.d || !pubJwk.x) throw new Error("generateEd25519KeyPair: JWK export failed");
  return {
    privateKey: Buffer.from(privJwk.d, "base64url"),
    publicKey: Buffer.from(pubJwk.x, "base64url"),
  };
}

export function signEd25519(privateKey: Buffer, message: Buffer): Buffer {
  assertKeyLength(privateKey, 32, "Ed25519 private key");
  const key = crypto.createPrivateKey({
    key: Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), privateKey]),
    format: "der",
    type: "pkcs8",
  });
  return crypto.sign(null, message, key);
}

export function verifyEd25519(
  publicKey: Buffer,
  message: Buffer,
  signature: Buffer
): boolean {
  assertKeyLength(publicKey, 32, "Ed25519 public key");
  const key = crypto.createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: publicKey.toString("base64url") },
    format: "jwk",
  });
  return crypto.verify(null, message, key, signature);
}
