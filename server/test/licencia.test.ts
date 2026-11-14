import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { atenderComandos, atenderWebhook } from "../src/telegram";
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
let cuerpos: Record<string, unknown>[] = [];

beforeEach(async () => {
  avisos = [];
  cuerpos = [];
  fetchOriginal = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("https://api.telegram.org/")) {
      const cuerpo = JSON.parse(String(init?.body || "{}")) as Record<string, unknown>;
      const metodo = url.split("?")[0].split("/").pop() || "";
      cuerpos.push({ ...cuerpo, _metodo: metodo });
      if (typeof cuerpo.text === "string" && cuerpo.text) avisos.push(cuerpo.text);
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
    return fetchOriginal(input, init);
  };
  await env.DB.prepare("DELETE FROM intentos").run();
  await env.DB.prepare("DELETE FROM sesiones").run();
  await env.DB.prepare("DELETE FROM solicitudes").run();
  await env.DB.prepare("DELETE FROM personas").run();
  await env.DB.prepare("DELETE FROM bot_estado").run();
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
    const reasignar = await env.DB.prepare(
      "SELECT id, tipo, estado FROM solicitudes WHERE tipo = 'reasignar'",
    ).all<{ id: string; tipo: string; estado: string }>();
    expect(reasignar.results).toHaveLength(1);
    expect(reasignar.results[0].estado).toBe("pendiente");
    const aprobada = await llamar(
      "/telegram/webhook",
      {
        callback_query: {
          id: "cb-reasignar",
          data: `aprobar:${reasignar.results[0].id}`,
          from: { id: 4242 },
          message: { message_id: 11, chat: { id: 4242 } },
        },
      },
      { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
    );
    expect(aprobada.respuesta.status).toBe(200);
    expect(avisos.some((texto) => texto.includes(codigo) && texto.includes("PC-AJENO"))).toBe(true);
    const enNuevo = await llamar("/v1/activar", {
      codigo,
      huella: HUELLA_B,
      equipo: "PC-AJENO",
    });
    expect(enNuevo.datos.carga?.ok).toBe(true);
    const enViejo = await llamar("/v1/estado", { codigo, huella: HUELLA_A, equipo: "PC-CASA" });
    expect(enViejo.datos.carga?.motivo).toBe("otro_equipo");
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

  it("recibe una solicitud, la aprueba con botones y liga el código a ese PC", async () => {
    const pedida = await llamar("/v1/solicitud", {
      nombre: "Ana García",
      oficina: "Sexta planta",
      huella: HUELLA_A,
      equipo: "PC-CASA",
    });
    expect(pedida.datos.carga?.motivo).toBe("enviada");
    expect(pedida.datos.carga?.ok).toBe(true);
    expect(JSON.stringify(pedida.datos.carga)).not.toContain("DRAKO-");
    expect(await firmaValida(pedida.datos.carga as Carga, pedida.datos.firma || "")).toBe(true);
    const aviso = cuerpos.find((cuerpo) => cuerpo.reply_markup);
    const teclado = aviso?.reply_markup as {
      inline_keyboard: { text: string; callback_data: string }[][];
    };
    expect(teclado.inline_keyboard[0].map((boton) => boton.text)).toEqual(["Aprobar", "Rechazar"]);
    expect(avisos.some((texto) => texto.includes("Sexta planta") && texto.includes("PC-CASA"))).toBe(true);
    const repetida = await llamar("/v1/solicitud", {
      nombre: "Ana García",
      oficina: "Sexta planta",
      huella: HUELLA_A,
      equipo: "PC-CASA",
    });
    expect(repetida.datos.carga?.motivo).toBe("ya_pendiente");

    const id = teclado.inline_keyboard[0][0].callback_data.split(":")[1];
    avisos = [];
    const ajeno = await llamar(
      "/telegram/webhook",
      {
        callback_query: {
          id: "cb-ajeno",
          data: `aprobar:${id}`,
          from: { id: 999 },
          message: { message_id: 4, chat: { id: 999 } },
        },
      },
      { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
    );
    expect(ajeno.respuesta.status).toBe(200);
    expect(avisos.some((texto) => texto.includes("DRAKO-"))).toBe(false);

    const aprobada = await llamar(
      "/telegram/webhook",
      {
        callback_query: {
          id: "cb-1",
          data: `aprobar:${id}`,
          from: { id: 4242 },
          message: { message_id: 7, chat: { id: 4242 } },
        },
      },
      { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
    );
    expect(aprobada.respuesta.status).toBe(200);
    const conCodigo = avisos.find((texto) => texto.includes("DRAKO-"));
    expect(conCodigo).toBeTruthy();
    expect(conCodigo).toContain("Pásaselo tú");
    expect(conCodigo).toContain("Sexta planta");
    const editado = avisos.find((texto) => texto.includes("siguiente mensaje"));
    expect(editado).toBeTruthy();
    expect(editado).not.toContain("DRAKO-");
    const codigo = (conCodigo || "").split("\n")[1];

    const otraVez = await llamar("/v1/solicitud", {
      nombre: "Ana García",
      oficina: "Sexta planta",
      huella: HUELLA_A,
      equipo: "PC-CASA",
    });
    expect(otraVez.datos.carga?.motivo).toBe("ya_aprobada");
    expect(JSON.stringify(otraVez.datos)).not.toContain(codigo);

    const activado = await llamar("/v1/activar", { codigo, huella: HUELLA_A, equipo: "PC-CASA" });
    expect(activado.datos.carga?.ok).toBe(true);
    expect(avisos.some((texto) => texto.includes("sesión iniciada") && texto.includes("Sexta planta"))).toBe(true);
    const intruso = await llamar("/v1/activar", { codigo, huella: HUELLA_B, equipo: "OTRO" });
    expect(intruso.datos.carga?.motivo).toBe("otro_equipo");

    const pedidaB = await llamar("/v1/solicitud", {
      nombre: "Luis",
      oficina: "Almacén",
      huella: HUELLA_B,
      equipo: "PC-LUIS",
    });
    expect(pedidaB.datos.carga?.motivo).toBe("enviada");
    const botonRechazo = cuerpos
      .map((cuerpo) => cuerpo.reply_markup as { inline_keyboard?: { callback_data: string }[][] } | undefined)
      .filter((marca) => marca?.inline_keyboard)
      .at(-1);
    const idB = botonRechazo?.inline_keyboard?.[0][1].callback_data.split(":")[1] || "";
    await llamar(
      "/telegram/webhook",
      {
        callback_query: {
          id: "cb-2",
          data: `rechazar:${idB}`,
          from: { id: 4242 },
          message: { message_id: 9, chat: { id: 4242 } },
        },
      },
      { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
    );
    expect(avisos.some((texto) => texto.includes("Solicitud rechazada") && texto.includes("Luis"))).toBe(true);
    avisos = [];
    await bot("/pendientes");
    expect(avisos[0]).toContain("Ana García");
    expect(avisos[0]).toContain("OTRO");
    expect(avisos[0]).not.toContain("Luis");
    avisos = [];
    await bot("/lista");
    expect(avisos[0]).toContain("Sexta planta");
    await bot(`/historial ${codigo}`);
    expect(avisos.at(-1)).toContain("Sexta planta");
  });

  it("limita las solicitudes por IP", async () => {
    for (let i = 0; i < 5; i += 1) {
      const alta = await llamar("/v1/solicitud", {
        nombre: `Persona ${i}`,
        oficina: "Oficina",
        huella: i.toString(16).padStart(2, "0").repeat(32),
        equipo: "PC",
      });
      expect(alta.datos.carga?.motivo).toBe("enviada");
    }
    const limitada = await llamar("/v1/solicitud", {
      nombre: "Una más",
      oficina: "Oficina",
      huella: "ff".repeat(32),
      equipo: "PC",
    });
    expect(limitada.datos.carga?.motivo).toBe("limitada");
  });

  it("el menú de botones crea, pagina, confirma y solo obedece a Drako", async () => {
    const inicio = await bot("/start");
    expect(inicio.respuesta.status).toBe(200);
    const altaComandos = cuerpos.find((cuerpo) => cuerpo._metodo === "setMyCommands");
    const comandos = (altaComandos?.commands || []) as { command: string }[];
    expect(comandos.map((comando) => comando.command)).toEqual([
      "start",
      "nuevo",
      "lista",
      "activos",
      "pendientes",
      "revocar",
      "historial",
      "borrar",
      "ayuda",
    ]);
    expect(altaComandos?.scope).toEqual({ type: "chat", chat_id: "4242" });
    const menu = cuerpos.find((cuerpo) => {
      const marca = cuerpo.reply_markup as { keyboard?: { text: string }[][] } | undefined;
      return Boolean(marca?.keyboard);
    });
    const teclas = ((menu?.reply_markup as { keyboard: { text: string }[][] }).keyboard || [])
      .flat()
      .map((boton) => boton.text);
    expect(teclas).toEqual([
      "➕ Nuevo acceso",
      "👥 Personas",
      "🟢 Conectados ahora",
      "⏳ Pendientes",
      "❓ Ayuda",
    ]);
    expect(avisos.at(-1)).not.toContain("/revocar");
    expect(avisos.at(-1)).not.toContain("Comandos de Drako Cam");

    avisos = [];
    await bot("/ayuda");
    expect(cuerpos.filter((cuerpo) => cuerpo._metodo === "setMyCommands").length).toBeGreaterThan(1);
    expect(avisos.at(-1)).not.toContain("/borrar");

    avisos = [];
    await bot("➕ Nuevo acceso");
    expect(avisos.at(-1)).toContain("Escribe el nombre");
    const pendiente = await env.DB.prepare("SELECT paso FROM bot_estado WHERE chat_id = ?")
      .bind("4242")
      .first<{ paso: string }>();
    expect(pendiente?.paso).toBe("nombre");

    avisos = [];
    await bot("Ana García");
    const creado = avisos.at(-1) || "";
    const codigo = creado.split("\n")[1] || "";
    expect(codigo).toMatch(/^DRAKO-[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$/);
    const entidad = cuerpos.at(-1)?.entities as { type: string; offset: number; length: number }[];
    expect(entidad).toEqual([{ type: "code", offset: creado.indexOf(codigo), length: codigo.length }]);
    const yaNo = await env.DB.prepare("SELECT COUNT(*) AS n FROM bot_estado").first<{ n: number }>();
    expect(Number(yaNo?.n)).toBe(0);

    avisos = [];
    await bot("esto no es un comando");
    expect(avisos.at(-1)).toContain("No entiendo");
    expect(avisos.at(-1)).not.toContain("/nuevo");
    expect((avisos.at(-1) || "").match(/\/lista/g)).toBeNull();

    avisos = [];
    await bot("👥 Personas");
    const inline = (cuerpos.at(-1)?.reply_markup as {
      inline_keyboard: { text: string; callback_data: string }[][];
    }).inline_keyboard;
    expect(inline[0].map((boton) => boton.text)).toEqual(["Historial", "Revocar", "Borrar"]);
    expect(avisos.at(-1)).toContain("Ana García");
    expect(avisos.at(-1)).toContain(codigo);

    await pulsar(inline[0][0].callback_data);
    expect(avisos.some((texto) => texto.includes("Historial de Ana García"))).toBe(true);

    await pulsar(inline[0][1].callback_data, "4242", 21);
    expect(avisos.some((texto) => texto.includes("¿Revocar el acceso de Ana García"))).toBe(true);
    const medio = await env.DB.prepare("SELECT revocado_en FROM personas WHERE codigo = ?")
      .bind(codigo)
      .first<{ revocado_en: number | null }>();
    expect(medio?.revocado_en ?? null).toBeNull();

    await pulsar("per:0", "4242", 21);
    const sigue = await env.DB.prepare("SELECT revocado_en FROM personas WHERE codigo = ?")
      .bind(codigo)
      .first<{ revocado_en: number | null }>();
    expect(sigue?.revocado_en ?? null).toBeNull();

    await pulsar(`rvy:${codigo}`, "4242", 22);
    const revocado = await env.DB.prepare("SELECT revocado_en FROM personas WHERE codigo = ?")
      .bind(codigo)
      .first<{ revocado_en: number | null }>();
    expect(revocado?.revocado_en).toBeTruthy();

    await pulsar(`bor:${codigo}`, "4242", 23);
    expect(avisos.some((texto) => texto.includes("¿Borrar a Ana García"))).toBe(true);
    await pulsar("per:0", "4242", 23);
    const aun = await env.DB.prepare("SELECT COUNT(*) AS n FROM personas WHERE codigo = ?")
      .bind(codigo)
      .first<{ n: number }>();
    expect(Number(aun?.n)).toBe(1);

    await pulsar(`boy:${codigo}`, "4242", 24);
    const fuera = await env.DB.prepare("SELECT COUNT(*) AS n FROM personas WHERE codigo = ?")
      .bind(codigo)
      .first<{ n: number }>();
    expect(Number(fuera?.n)).toBe(0);

    await bot("/nuevo Luis");
    const codigoLuis = (avisos.at(-1) || "").split("\n")[1] || "";
    avisos = [];
    const ajeno = await pulsar(`rvy:${codigoLuis}`, "999", 30);
    expect(ajeno.respuesta.status).toBe(200);
    expect(avisos).toEqual([]);
    const luis = await env.DB.prepare("SELECT revocado_en FROM personas WHERE codigo = ?")
      .bind(codigoLuis)
      .first<{ revocado_en: number | null }>();
    expect(luis?.revocado_en ?? null).toBeNull();

    await bot("➕ Nuevo acceso");
    await env.DB.prepare("UPDATE bot_estado SET expira_en = 1").run();
    avisos = [];
    await bot("Persona Caducada");
    expect(avisos.at(-1)).toContain("No entiendo");
    const fantasma = await env.DB.prepare("SELECT COUNT(*) AS n FROM personas WHERE nombre = ?")
      .bind("Persona Caducada")
      .first<{ n: number }>();
    expect(Number(fantasma?.n)).toBe(0);

    for (const nombre of ["Bea", "Ciro", "Dina", "Eva"]) {
      await bot(`/nuevo ${nombre}`);
    }
    avisos = [];
    await bot("👥 Personas");
    const pagina = cuerpos.at(-1)?.reply_markup as {
      inline_keyboard: { text: string; callback_data: string }[][];
    };
    const siguiente = pagina.inline_keyboard.flat().find((boton) => boton.text === "Siguiente");
    expect(siguiente?.callback_data).toBe("per:1");
    avisos = [];
    await pulsar(siguiente?.callback_data || "", "4242", 40);
    expect(avisos.at(-1)).toContain("página 2");

    const pedida = await llamar("/v1/solicitud", {
      nombre: "Olga",
      oficina: "Norte",
      huella: "ee".repeat(32),
      equipo: "PC-OLGA",
    });
    expect(pedida.datos.carga?.motivo).toBe("enviada");
    avisos = [];
    await bot("⏳ Pendientes");
    const pendientes = cuerpos.at(-1)?.reply_markup as {
      inline_keyboard: { text: string; callback_data: string }[][];
    };
    expect(pendientes.inline_keyboard[0].map((boton) => boton.text)).toEqual(["Aprobar", "Rechazar"]);
    expect(avisos.at(-1)).toContain("Olga");

    const ok = await llamar(
      "/telegram/comandos",
      {},
      { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
    );
    expect(ok.respuesta.status).toBe(200);
    expect(ok.datos).toEqual({ ok: true });
    const mal = await llamar(
      "/telegram/comandos",
      {},
      { "X-Telegram-Bot-Api-Secret-Token": "otro" },
    );
    expect(mal.respuesta.status).toBe(401);
    const metodo = await llamar("/telegram/comandos", null, {}, "GET");
    expect(metodo.respuesta.status).toBe(405);

    const vacio = await atenderComandos(
      new Request("https://licencias.test/telegram/comandos", { method: "POST" }),
      { ...env, TELEGRAM_WEBHOOK_SECRET: "" },
    );
    expect(vacio.status).toBe(503);
  });
});

async function pulsar(data: string, chat = "4242", messageId = 11) {
  return llamar(
    "/telegram/webhook",
    {
      callback_query: {
        id: `cb-${messageId}-${data.slice(0, 12)}`,
        data,
        from: { id: Number(chat) },
        message: { message_id: messageId, chat: { id: Number(chat) } },
      },
    },
    { "X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba-webhook" },
  );
}
