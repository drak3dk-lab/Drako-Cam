/**
 * Genera la semilla de firma y la clave pública.
 * No escribe nada en disco. La semilla solo se pega en `wrangler secret put`.
 */
import { generateKeyPairSync, randomBytes } from "node:crypto";

const PREFIJO = Buffer.from("302e020100300506032b657004220420", "hex");

const { publicKey, privateKey } = generateKeyPairSync("ed25519");
const pkcs8 = privateKey.export({ type: "pkcs8", format: "der" });
const spki = publicKey.export({ type: "spki", format: "der" });
const semilla = pkcs8.subarray(pkcs8.length - 32);
const publica = spki.subarray(spki.length - 32);
const reconstruida = Buffer.concat([PREFIJO, semilla]);
if (!reconstruida.equals(pkcs8)) {
  console.error("No se pudo preparar la semilla. No uses esta salida.");
  process.exit(1);
}

const webhook = randomBytes(24).toString("base64url");

console.log("Copia cada valor donde se indica. No los subas a GitHub ni los pegues en un chat.\n");
console.log("1) Secreto SIGNING_SEED");
console.log("   Comando: npx wrangler secret put SIGNING_SEED");
console.log(semilla.toString("base64"));
console.log("\n2) Clave pública, para app/drako/licencia_config.py (CLAVE_PUBLICA_HEX)");
console.log(publica.toString("hex"));
console.log("\n3) Secreto TELEGRAM_WEBHOOK_SECRET");
console.log("   Comando: npx wrangler secret put TELEGRAM_WEBHOOK_SECRET");
console.log(webhook);
console.log("\nCierra esta ventana cuando los hayas guardado en los secretos y en la app.");
