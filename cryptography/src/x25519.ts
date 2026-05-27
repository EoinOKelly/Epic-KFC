import * as crypto from "node:crypto";
import { assertKeyLength } from "./bufferUtils";

export interface X25519KeyPair {
  publicKey: Buffer;
  privateKey: Buffer;
}

export function generateX25519KeyPair(): X25519KeyPair {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("x25519");
  const privJwk = privateKey.export({ format: "jwk" }) as { d?: string };
  const pubJwk = publicKey.export({ format: "jwk" }) as { x?: string };
  if (!privJwk.d || !pubJwk.x) throw new Error("generateX25519KeyPair: JWK export failed");
  return {
    privateKey: Buffer.from(privJwk.d, "base64url"),
    publicKey: Buffer.from(pubJwk.x, "base64url"),
  };
}

export function x25519Dh(privateKey: Buffer, publicKey: Buffer): Buffer {
  assertKeyLength(privateKey, 32, "X25519 private key");
  assertKeyLength(publicKey, 32, "X25519 public key");

  const priv = crypto.createPrivateKey({
    key: Buffer.concat([Buffer.from("302e020100300506032b656e04220420", "hex"), privateKey]),
    format: "der",
    type: "pkcs8",
  });
  const pub = crypto.createPublicKey({
    key: Buffer.concat([Buffer.from("302a300506032b656e032100", "hex"), publicKey]),
    format: "der",
    type: "spki",
  });
  return Buffer.from(crypto.diffieHellman({ privateKey: priv, publicKey: pub }));
}
