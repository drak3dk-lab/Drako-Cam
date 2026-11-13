import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { atenderWebhook } from "../src/telegram";
import { canonico, firmarCarga, prepararFirmante } from "../src/crypto";
import { leerLugar } from "../src/lugar";
import worker from "../src/index";
import type { Carga } from "../src/tipos";

const VECTOR =
  '{"accion":"activar","codigo_hash":"abc","emitido":1760000000,"estado":"activa","expira":1760000180,"gracia_horas":24,"huella":"aa","latido_segundos":60,"mensaje":"Acceso concedido en București.","motivo":"ok","ok":true,"persona":"José","sesion":"s1","v":1}';
const FIRMA_VECTOR =
  "LWQ5410GLZlD8ULKr9UWv1X2iNuGynZFU+0aHPQr3Z6pO548OsrNQ81XiSlQPqdX0er9gFeOp+ofkyyWvl0AAQ==";
const PUBLICA_VECTOR = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737";

const HUELLA_A = "ab".repeat(32);
const HUELLA_B = "cd".repeat(32);
const AHORA = "1760000000";

let fetchOriginal: typeof fetch;
let avisos: string[] = [];

beforeEach(async () => {
  avisos = [];
  fetchOriginal = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("https://api.telegram.org/")) {
      const cuerpo = JSON.parse(String(init?.body || "{}")) as { text?: string };
      avisos.push(String(cuerpo.text || ""));
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
    return fetchOriginal(input, init);
  };
  await env.DB.prepare("DELETE FROM intentos").run();
  await env.DB.prepare("DELETE FROM sesiones").run();
  await env.DB.prepare("DELETE FROM personas").run();
});

afterEach(() => {
  globalThis.fetch = fetchOriginal;
});

async function llamar(
  ruta: string,
  cuerpo: unknown,
  cabeceras: Record<string, string> = {},
  metodo = "POST",
) {
  const ctx = createExecutionContext();
  const peticion = new Request(`https://licencias.test${ruta}`, {
    method: metodo,
    headers: {
      "content-type": "application/json",
      "x-drako-ip": "89.38.1.2",
      "x-drako-pais": "RO",
      "x-drako-ciudad": "Bucharest",
      "x-drako-ahora": AHORA,
      ...cabeceras,
    },
    body: metodo === "GET" ? undefined : JSON.stringify(cuerpo),
  });
  const respuesta = await worker.fetch(peticion, env, ctx);
  await waitOnExecutionContext(ctx);
  const texto = await respuesta.text();
  let datos: { carga?: Carga; firma?: string; error?: string } = {};
  if (texto) datos = JSON.parse(texto) as typeof datos;
  return { respuesta, datos };
}

async function firmaValida(carga: Carga, firma: string): Promise<boolean> {
  const firmante = await prepararFirmante(env.SIGNING_SEED);
  const clave = await crypto.subtle.importKey(
    "raw",
    firmante.publica,
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  const bytes = Uint8Array.from(atob(firma), (c) => c.charCodeAt(0));
  return crypto.subtle.verify(
    { name: "Ed25519" },
    clave,
    bytes,
    new TextEncoder().encode(canonico(carga)),
  );
}

async function bot(texto: string, chat = "4242", secreto = "secreto-de-prueba-webhook") {
  return llamar(
    "/telegram/webhook",
    { message: { text: texto, chat: { id: Number(chat) } } },
    { "X-Telegram-Bot-Api-Secret-Token": secreto },
  );
}

describe("firma", () => {
  it("reproduce el vector Ed25519 compartido con la app", async () => {
    const carga = JSON.parse(VECTOR) as Carga;
    expect(canonico(carga)).toBe(VECTOR);
    const firmante = await prepararFirmante(env.SIGNING_SEED);
    expect([...firmante.publica].map((b) => b.toString(16).padStart(2, "0")).join("")).toBe(
      PUBLICA_VECTOR,
    );
    expect(await firmarCarga(firmante, carga)).toBe(FIRMA_VECTOR);
    expect(await firmaValida(carga, FIRMA_VECTOR)).toBe(true);
  });

  it("ignora la ubicación de prueba si no está el modo de prueba", () => {
    const peticion = new Request("https://licencias.test/v1/estado", {
      headers: { "x-drako-pais": "RO", "x-drako-ip": "1.2.3.4", "x-drako-ahora": "10" },
    });
    const lugar = leerLugar(peticion, {});
    expect(lugar.pais).toBe("");
    expect(lugar.ip).toBe("");
    expect(lugar.ahora).not.toBe(10);
    const conCf = new Request("https://licencias.test/v1/estado");
    Object.defineProperty(conCf, "cf", { value: { country: "RO", city: "București" } });
    expect(leerLugar(conCf, {}).ciudad).toBe("București");
  });
});

describe("acceso", () => {
  it("responde salud y rechaza rutas o métodos desconocidos", async () => {
    const salud = await llamar("/v1/salud", null, {}, "GET");
    expect(salud.respuesta.status).toBe(200);
    expect(salud.datos).toEqual({ ok: true, servicio: "drako-cam-licencias" });
    const metodo = await llamar("/v1/activar", {}, {}, "GET");
    expect(metodo.respuesta.status).toBe(405);
    const ruta = await llamar("/v1/no-existe", {});
    expect(ruta.respuesta.status).toBe(404);
    const jsonRoto = await llamar("/v1/activar", "no-json");
    expect(jsonRoto.respuesta.status).toBe(400);
  });

  it("crea un código, lo liga al equipo y firma la concesión", async () => {
    const alta = await bot("/nuevo Ana García");
    expect(alta.respuesta.status).toBe(200);
    expect(avisos[0]).toContain("Ana García");
    const codigo = avisos[0].split("\n")[1];
    expect(codigo).toMatch(/^DRAKO-[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$/);

    const activado = await llamar("/v1/activar", {
      codigo,
      huella: HUELLA_A,
      equipo: "PC-CASA",
    });
    expect(activado.respuesta.status).toBe(200);
    const carga = activado.datos.carga as Carga;
    expect(carga.ok).toBe(true);
    expect(carga.persona).toBe("Ana García");
    expect(carga.estado).toBe("activa");
    expect(carga.huella).toBe(HUELLA_A);
    expect(await firmaValida(carga, activado.datos.firma || "")).toBe(true);
    expect(avisos.some((texto) => texto.includes("sesión iniciada"))).toBe(true);
    expect(avisos.some((texto) => texto.includes("Bucharest, RO"))).toBe(true);
    expect(avisos.some((texto) => texto.includes("Europe/Bucharest"))).toBe(true);
    expect(avisos.some((texto) => texto.includes("89.38.1.2"))).toBe(true);

    const otro = await llamar("/v1/activar", {
      codigo,
      huella: HUELLA_B,
      equipo: "PC-AJENO",
    });
    expect(otro.datos.carga?.motivo).toBe("otro_equipo");
    expect(otro.datos.carga?.ok).toBe(false);
    expect(await firmaValida(otro.datos.carga as Carga, otro.datos.firma || "")).toBe(true);
    expect(avisos.some((texto) => texto.includes("otro equipo"))).toBe(true);

    const estado = await llamar("/v1/estado", { codigo, huella: HUELLA_A, equipo: "PC-CASA" });
    expect(estado.datos.carga?.ok).toBe(true);
    expect(estado.datos.carga?.motivo).toBe("ok");
    const sesiones = await env.DB.prepare("SELECT COUNT(*) AS n FROM sesiones").first<{ n: number }>();
    expect(Number(sesiones?.n)).toBe(1);
  });

  it("late el corazón, cierra con duración y deja fuera un código revocado", async () => {
    await bot("/nuevo Luis");
    const codigo = avisos.at(-1)?.split("\n")[1] || "";
    const activado = await llamar("/v1/activar", { codigo, huella: HUELLA_A, equipo: "PC-LUIS" });
    const sesion = activado.datos.carga?.sesion || "";

    const latido = await llamar(
      "/v1/latido",
      { codigo, huella: HUELLA_A, equipo: "PC-LUIS", sesion },
      { "x-drako-ahora": "1760000060" },
    );
    expect(latido.datos.carga?.ok).toBe(true);
    const fila = await env.DB.prepare("SELECT ultimo_latido FROM sesiones WHERE id = ?")
      .bind(sesion)
      .first<{ ultimo_latido: number }>();
    expect(Number(fila?.ultimo_latido)).toBe(1760000060);

    const cierre = await llamar(
      "/v1/cerrar",
      { codigo, huella: HUELLA_A, equipo: "PC-LUIS", sesion },
      { "x-drako-ahora": "1760000100" },
    );
    expect(cierre.datos.carga?.motivo).toBe("ok");
    expect(cierre.datos.carga?.estado).toBe("cerrada");
    expect(avisos.some((texto) => texto.includes("sesión cerrada") && texto.includes("1 min 40 s"))).toBe(
      true,
    );
    const repetido = await llamar(
      "/v1/cerrar",
      { codigo, huella: HUELLA_A, equipo: "PC-LUIS", sesion },
      { "x-drako-ahora": "1760000120" },
    );
    expect(repetido.datos.carga?.motivo).toBe("ya_cerrada");

    const otra = await llamar("/v1/activar", {
      codigo,
      huella: HUELLA_A,
      equipo: "PC-LUIS",
    }, { "x-drako-ahora": "1760000200" });
    await bot(`/revocar ${codigo}`, "4242", "secreto-de-prueba-webhook");
    const cortado = await llamar(
      "/v1/latido",
      { codigo, huella: HUELLA_A, equipo: "PC-LUIS", sesion: otra.datos.carga?.sesion },
      { "x-drako-ahora": "1760000300" },
    );
    expect(cortado.datos.carga?.motivo).toBe("revocado");
    expect(cortado.datos.carga?.ok).toBe(false);
    expect(avisos.some((texto) => texto.includes("código revocado"))).toBe(true);

    const historial = await bot(`/historial ${codigo}`);
    expect(historial.respuesta.status).toBe(200);
    expect(avisos.at(-1)).toContain("Luis");
    expect(avisos.at(-1)).toContain("Bucharest");
  });

  it("avisa de un código desconocido, limita intentos y solo obedece a Drako", async () => {
    const falso = "DRAKO-AAAA-BBBB-CCCC-DDDD";
    for (let i = 0; i < 3; i += 1) {
      const rechazo = await llamar("/v1/activar", { codigo: falso, huella: HUELLA_A, equipo: "PC" });
      expect(rechazo.datos.carga?.motivo).toBe("desconocido");
    }
    expect(avisos.filter((texto) => texto.includes("desconocido"))).toHaveLength(3);
    const limitado = await llamar("/v1/activar", { codigo: falso, huella: HUELLA_A, equipo: "PC" });
    expect(limitado.datos.carga?.motivo).toBe("limitada");
    expect(avisos.filter((texto) => texto.includes("desconocido"))).toHaveLength(3);

    avisos = [];
    const ajeno = await bot("/lista", "999");
    expect(ajeno.respuesta.status).toBe(200);
    expect(avisos).toEqual([]);
    const secreto = await bot("/lista", "4242", "otro-secreto");
    expect(secreto.respuesta.status).toBe(401);

    const vacio = await atenderWebhook(
      new Request("https://licencias.test/telegram/webhook", { method: "POST", body: "{}" }),
      { ...env, TELEGRAM_WEBHOOK_SECRET: "" },
      1,
    );
    expect(vacio.status).toBe(503);
  });

  it("lista activos, borra el historial y no muestra sesiones sin latido", async () => {
    await bot("/nuevo Nia");
    const codigo = avisos[0].split("\n")[1];
    await llamar("/v1/activar", { codigo, huella: HUELLA_A, equipo: "PORTATIL" });
    avisos = [];
    await bot("/activos");
    expect(avisos[0]).toContain("Nia");
    expect(avisos[0]).toContain("PORTATIL");

    avisos = [];
    await bot("/activos", "4242", "secreto-de-prueba-webhook");
    const despues = await llamar(
      "/v1/estado",
      { codigo, huella: HUELLA_A, equipo: "PORTATIL" },
      { "x-drako-ahora": String(1760000000 + 181) },
    );
    expect(despues.datos.carga?.ok).toBe(true);
    avisos = [];
    await bot("/activos");
    expect(avisos[0]).toContain("nadie está usando");

    avisos = [];
    await bot(`/borrar ${codigo}`);
    expect(avisos[0]).toContain("Se eliminó a Nia");
    const perdido = await llamar("/v1/estado", { codigo, huella: HUELLA_A, equipo: "PORTATIL" });
    expect(perdido.datos.carga?.motivo).toBe("desconocido");
    const lista = await bot("/lista");
    expect(avisos.at(-1)).toContain("Todavía no hay códigos");
    expect(lista.respuesta.status).toBe(200);
  });
});
