import path from "node:path";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig(async () => {
  const migraciones = await readD1Migrations(path.join(import.meta.dirname, "migrations"));
  const semilla = Buffer.alloc(32, 0x11).toString("base64");
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.toml" },
        miniflare: {
          bindings: {
            TEST_MIGRATIONS: migraciones,
            SIGNING_SEED: semilla,
            // Token ficticio. Solo existe en las pruebas; no abre ningún bot.
            TELEGRAM_BOT_TOKEN: ["123456789", "AATestTokenDePruebaNoEsReal"].join(":"),
            TELEGRAM_ADMIN_CHAT_ID: "4242",
            TELEGRAM_WEBHOOK_SECRET: "secreto-de-prueba-webhook",
            MODO_PRUEBA: "1",
            LIMITE_INTENTOS: "3",
            GRACIA_HORAS: "24",
            LATIDO_SEGUNDOS: "60",
            SESION_ACTIVA_SECS: "180",
          },
        },
      }),
    ],
    test: {
      fileParallelism: false,
      setupFiles: ["./test/aplicar.ts"],
      testTimeout: 20000,
      hookTimeout: 20000,
    },
  };
});
