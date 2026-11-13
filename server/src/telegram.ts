import { enviarTelegram, formatearHora, llamarTelegram, textoDuracion, textoLugar, textoOficina } from "./avisos";
import { generarCodigo, iguales, limpiarNombre, normalizarCodigo } from "./crypto";
import { contestarCallback } from "./solicitud";
import type { Env, Persona, Sesion } from "./tipos";

const TTL_ESTADO_S = 600;
const POR_PAGINA = 4;

const MENU_CORTO =
  "Menú de Drako Cam. Elige un botón. Los comandos siguen en el menú de Telegram, junto al campo de texto.";
const MENU_DESCONOCIDO = "No entiendo ese mensaje. Elige una acción del menú.";
const PREGUNTA_NOMBRE = [
  "Escribe el nombre de la persona.",
  "Ejemplo: Ana García",
  "Tienes 10 minutos. Si pasa el tiempo, pulsa otra vez Nuevo acceso.",
].join("\n");

const BOTONES: Record<string, "nuevo" | "personas" | "activos" | "pendientes" | "ayuda"> = {
  "➕ Nuevo acceso": "nuevo",
  "👥 Personas": "personas",
  "🟢 Conectados ahora": "activos",
  "⏳ Pendientes": "pendientes",
  "❓ Ayuda": "ayuda",
};

export const COMANDOS_BOT = [
  { command: "start", description: "Abrir el menú" },
  { command: "nuevo", description: "Crear un código: /nuevo Nombre" },
  { command: "lista", description: "Ver las personas" },
  { command: "activos", description: "Ver quién está conectado" },
  { command: "pendientes", description: "Ver solicitudes sin decidir" },
  { command: "revocar", description: "Revocar un código" },
  { command: "historial", description: "Ver el historial de un código" },
  { command: "borrar", description: "Borrar a una persona y su historial" },
  { command: "ayuda", description: "Mostrar el menú" },
];

type RespuestaBot = {
  texto: string;
  extra?: Record<string, unknown>;
};

type Consulta = {
  id: string;
  data: string;
  chatId: string;
  messageId: number | null;
};

function jsonVacio(): Response {
  return new Response("", { status: 200 });
}

export function tecladoPrincipal(): Record<string, unknown> {
  return {
    keyboard: [
      [{ text: "➕ Nuevo acceso" }, { text: "👥 Personas" }],
      [{ text: "🟢 Conectados ahora" }, { text: "⏳ Pendientes" }],
      [{ text: "❓ Ayuda" }],
    ],
    resize_keyboard: true,
    is_persistent: true,
  };
}

function conMenu(texto: string): RespuestaBot {
  return { texto, extra: { reply_markup: tecladoPrincipal() } };
}

function plano(texto: string, extra?: Record<string, unknown>): RespuestaBot {
  return extra ? { texto, extra } : { texto };
}

function extraCodigo(texto: string, codigo: string): Record<string, unknown> {
  const offset = texto.indexOf(codigo);
  if (offset < 0) return {};
  return { entities: [{ type: "code", offset, length: codigo.length }] };
}

export async function publicarComandos(env: Env): Promise<boolean> {
  const chat = (env.TELEGRAM_ADMIN_CHAT_ID || "").trim();
  const cuerpo: Record<string, unknown> = { commands: COMANDOS_BOT };
  if (chat) cuerpo.scope = { type: "chat", chat_id: chat };
  return llamarTelegram(env, "setMyCommands", cuerpo);
}

export async function atenderComandos(request: Request, env: Env): Promise<Response> {
  const secreto = (env.TELEGRAM_WEBHOOK_SECRET || "").trim();
  const token = (env.TELEGRAM_BOT_TOKEN || "").trim();
  if (!secreto || !token) return Response.json({ error: "servidor" }, { status: 503 });
  const recibido = request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
  if (!iguales(recibido, secreto)) return Response.json({ error: "no autorizado" }, { status: 401 });
  const publicado = await publicarComandos(env);
  return Response.json({ ok: publicado }, { status: publicado ? 200 : 502 });
}

export async function atenderWebhook(
  request: Request,
  env: Env,
  ahora: number,
): Promise<Response> {
  const secreto = (env.TELEGRAM_WEBHOOK_SECRET || "").trim();
  const chatAdmin = (env.TELEGRAM_ADMIN_CHAT_ID || "").trim();
  if (!secreto || !chatAdmin) {
    return Response.json({ error: "servidor" }, { status: 503 });
  }
  const recibido = request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
  if (!iguales(recibido, secreto)) {
    return Response.json({ error: "no autorizado" }, { status: 401 });
  }
  let update: {
    message?: { text?: unknown; chat?: { id?: unknown } };
    callback_query?: {
      id?: unknown;
      data?: unknown;
      from?: { id?: unknown };
      message?: { message_id?: unknown; chat?: { id?: unknown } };
    };
  };
  try {
    update = (await request.json()) as typeof update;
  } catch {
    return jsonVacio();
  }
  const consulta = update.callback_query;
  if (consulta && typeof consulta.id === "string") {
    const chatId = consulta.message?.chat?.id;
    const desde = consulta.from?.id;
    const esAdmin = iguales(String(chatId ?? ""), chatAdmin) && iguales(String(desde ?? ""), chatAdmin);
    if (!esAdmin) return jsonVacio();
    const datos: Consulta = {
      id: consulta.id,
      data: typeof consulta.data === "string" ? consulta.data : "",
      chatId: String(chatId),
      messageId: typeof consulta.message?.message_id === "number" ? consulta.message.message_id : null,
    };
    if (/^(aprobar|rechazar):/i.test(datos.data)) {
      await contestarCallback(env, datos, ahora);
    } else {
      await contestarAccion(env, datos, ahora);
    }
    return jsonVacio();
  }
  const mensaje = update.message;
  const texto = typeof mensaje?.text === "string" ? mensaje.text.trim() : "";
  const chatId = mensaje?.chat?.id;
  if (!texto || chatId === undefined || chatId === null) return jsonVacio();
  if (!iguales(String(chatId), chatAdmin)) return jsonVacio();
  const respuesta = await orden(env, texto, ahora, String(chatId));
  await enviarTelegram(env, respuesta.texto, respuesta.extra ?? {});
  return jsonVacio();
}

async function orden(env: Env, texto: string, ahora: number, chatId: string): Promise<RespuestaBot> {
  await limpiarEstados(env, ahora);
  const boton = BOTONES[texto];
  if (boton) {
    await borrarEstado(env, chatId);
    return actuar(env, boton, "", ahora, chatId);
  }
  const coincidencia = texto.match(/^\/([a-z]+)(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]+))?$/i);
  if (coincidencia) {
    const comando = coincidencia[1].toLowerCase();
    const argumento = (coincidencia[2] || "").trim();
    if (comando === "nuevo" && !argumento) {
      await guardarEstado(env, chatId, "nombre", ahora + TTL_ESTADO_S);
      return conMenu(PREGUNTA_NOMBRE);
    }
    await borrarEstado(env, chatId);
    return actuar(env, comando, argumento, ahora, chatId);
  }
  const estado = await leerEstado(env, chatId);
  if (estado && estado.paso === "nombre" && estado.expira_en >= ahora) {
    const creada = await crear(env, texto, ahora);
    if (creada.texto.startsWith("Escribe el nombre")) return conMenu(PREGUNTA_NOMBRE);
    await borrarEstado(env, chatId);
    return creada;
  }
  await borrarEstado(env, chatId);
  return conMenu(MENU_DESCONOCIDO);
}

async function actuar(
  env: Env,
  comando: string,
  argumento: string,
  ahora: number,
  chatId: string,
): Promise<RespuestaBot> {
  if (comando === "ayuda" || comando === "start" || comando === "help") {
    await publicarComandos(env);
    return conMenu(MENU_CORTO);
  }
  if (comando === "nuevo") {
    if (!argumento) {
      await guardarEstado(env, chatId, "nombre", ahora + TTL_ESTADO_S);
      return conMenu(PREGUNTA_NOMBRE);
    }
    return crear(env, argumento, ahora);
  }
  if (comando === "lista" || comando === "personas") return vistaPersonas(env, 0);
  if (comando === "revocar") return plano(await revocar(env, argumento, ahora));
  if (comando === "activos") return plano(await activos(env, ahora));
  if (comando === "historial") return plano(await historial(env, argumento));
  if (comando === "pendientes") return await vistaPendientes(env);
  if (comando === "borrar") return plano(await borrar(env, argumento));
  return conMenu(MENU_DESCONOCIDO);
}

async function contestarAccion(env: Env, datos: Consulta, ahora: number): Promise<void> {
  await llamarTelegram(env, "answerCallbackQuery", { callback_query_id: datos.id });
  const separador = datos.data.indexOf(":");
  const accion = separador < 0 ? datos.data : datos.data.slice(0, separador);
  const argumento = separador < 0 ? "" : datos.data.slice(separador + 1);
  if (accion === "per") {
    const pagina = Number(argumento);
    const vista = await vistaPersonas(env, Number.isFinite(pagina) ? pagina : 0);
    await mostrar(env, datos, vista);
    return;
  }
  if (accion === "his") {
    await enviarTelegram(env, await historial(env, argumento));
    return;
  }
  if (accion === "rvo" || accion === "bor") {
    const persona = await buscarPersona(env, argumento);
    if (!persona) {
      await mostrar(env, datos, plano("No existe ese código."));
      return;
    }
    const texto = accion === "rvo"
      ? `¿Revocar el acceso de ${persona.nombre}?\n${persona.codigo}\nDejará de poder entrar.`
      : `¿Borrar a ${persona.nombre} y su historial?\n${persona.codigo}\nEsta acción no se deshace.`;
    const si = accion === "rvo" ? "rvy" : "boy";
    const etiqueta = accion === "rvo" ? "Sí, revocar" : "Sí, borrar";
    await mostrar(env, datos, plano(texto, {
      reply_markup: {
        inline_keyboard: [[
          { text: etiqueta, callback_data: `${si}:${persona.codigo}` },
          { text: "Cancelar", callback_data: "per:0" },
        ]],
      },
    }));
    return;
  }
  if (accion === "rvy") {
    await mostrar(env, datos, plano(await revocar(env, argumento, ahora), tecladoVolver()));
    return;
  }
  if (accion === "boy") {
    await mostrar(env, datos, plano(await borrar(env, argumento), tecladoVolver()));
    return;
  }
}

function tecladoVolver(): Record<string, unknown> {
  return { reply_markup: { inline_keyboard: [[{ text: "Volver", callback_data: "per:0" }]] } };
}

async function mostrar(env: Env, datos: Consulta, respuesta: RespuestaBot): Promise<void> {
  const texto = respuesta.texto.slice(0, 4000);
  if (datos.messageId !== null) {
    await llamarTelegram(env, "editMessageText", {
      chat_id: datos.chatId,
      message_id: datos.messageId,
      text: texto,
      ...(respuesta.extra ?? {}),
    });
    return;
  }
  await enviarTelegram(env, texto, respuesta.extra ?? {});
}

async function guardarEstado(env: Env, chatId: string, paso: string, expira: number): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO bot_estado (chat_id, paso, expira_en) VALUES (?, ?, ?)
     ON CONFLICT(chat_id) DO UPDATE SET paso = excluded.paso, expira_en = excluded.expira_en`,
  )
    .bind(chatId, paso, expira)
    .run();
}

async function borrarEstado(env: Env, chatId: string): Promise<void> {
  await env.DB.prepare("DELETE FROM bot_estado WHERE chat_id = ?").bind(chatId).run();
}

async function leerEstado(
  env: Env,
  chatId: string,
): Promise<{ paso: string; expira_en: number } | null> {
  return env.DB.prepare("SELECT paso, expira_en FROM bot_estado WHERE chat_id = ?")
    .bind(chatId)
    .first<{ paso: string; expira_en: number }>();
}

async function limpiarEstados(env: Env, ahora: number): Promise<void> {
  await env.DB.prepare("DELETE FROM bot_estado WHERE expira_en < ?").bind(ahora).run();
}

async function crear(env: Env, argumento: string, ahora: number): Promise<RespuestaBot> {
  const nombre = limpiarNombre(argumento);
  if (!nombre) return plano("Escribe el nombre de la persona.\nEjemplo: /nuevo Ana García");
  for (let intento = 0; intento < 5; intento += 1) {
    const codigo = generarCodigo();
    try {
      await env.DB.prepare(
        "INSERT INTO personas (codigo, nombre, creado_en) VALUES (?, ?, ?)",
      )
        .bind(codigo, nombre, ahora)
        .run();
      const texto = [
        `Código creado para ${nombre}:`,
        codigo,
        "Dáselo a esa persona. Queda ligado al primer equipo que lo active.",
      ].join("\n");
      return plano(texto, extraCodigo(texto, codigo));
    } catch {
      // Choque muy raro de código: se prueba otro.
    }
  }
  return plano("No se pudo crear el código. Prueba otra vez.");
}

function lineaPersona(persona: Persona): string {
  const estado = persona.revocado_en ? "revocado" : "activo";
  const equipo = persona.equipo ? ` — ${persona.equipo}` : " — sin equipo";
  const oficina = ` — ${textoOficina(persona.oficina)}`;
  return `• ${persona.nombre} — ${persona.codigo} — ${estado}${oficina}${persona.revocado_en ? "" : equipo}`;
}

async function vistaPersonas(env: Env, pagina: number): Promise<RespuestaBot> {
  const cuenta = await env.DB.prepare("SELECT COUNT(*) AS n FROM personas").first<{ n: number }>();
  const total = Number(cuenta?.n || 0);
  if (!total) {
    return conMenu("Todavía no hay códigos. Crea uno con /nuevo <nombre>.");
  }
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const actual = Math.min(paginas - 1, Math.max(0, Math.floor(pagina)));
  const filas = await env.DB.prepare(
    `SELECT codigo, nombre, oficina, revocado_en, huella, equipo
     FROM personas ORDER BY rowid DESC LIMIT ? OFFSET ?`,
  )
    .bind(POR_PAGINA, actual * POR_PAGINA)
    .all<Persona>();
  const personas = filas.results || [];
  const lineas = personas.map(lineaPersona);
  const teclas: { text: string; callback_data: string }[][] = personas.map((persona) => [
    { text: "Historial", callback_data: `his:${persona.codigo}` },
    { text: "Revocar", callback_data: `rvo:${persona.codigo}` },
    { text: "Borrar", callback_data: `bor:${persona.codigo}` },
  ]);
  const navegacion: { text: string; callback_data: string }[] = [];
  if (actual > 0) navegacion.push({ text: "Anterior", callback_data: `per:${actual - 1}` });
  if (actual + 1 < paginas) navegacion.push({ text: "Siguiente", callback_data: `per:${actual + 1}` });
  if (navegacion.length) teclas.push(navegacion);
  const cabecera = paginas > 1
    ? `Personas (${total}), página ${actual + 1} de ${paginas}:`
    : `Personas (${total}):`;
  return plano([cabecera, ...lineas].join("\n"), { reply_markup: { inline_keyboard: teclas } });
}

async function buscarPersona(env: Env, argumento: string): Promise<Persona | null> {
  const codigo = normalizarCodigo(argumento);
  if (!codigo) return null;
  return env.DB.prepare("SELECT * FROM personas WHERE codigo = ?").bind(codigo).first<Persona>();
}

async function revocar(env: Env, argumento: string, ahora: number): Promise<string> {
  const codigo = normalizarCodigo(argumento);
  if (!codigo) return "Escribe el código.\nEjemplo: /revocar DRAKO-XXXX-XXXX-XXXX-XXXX";
  const persona = await env.DB.prepare("SELECT * FROM personas WHERE codigo = ?")
    .bind(codigo)
    .first<Persona>();
  if (!persona) return "No existe ese código.";
  if (persona.revocado_en) return `El código de ${persona.nombre} ya estaba revocado.`;
  const abiertas = await env.DB.prepare(
    "SELECT inicio FROM sesiones WHERE codigo = ? AND fin IS NULL",
  )
    .bind(codigo)
    .all<{ inicio: number }>();
  await env.DB.batch([
    env.DB.prepare("UPDATE personas SET revocado_en = ? WHERE codigo = ?").bind(ahora, codigo),
    env.DB.prepare(
      `UPDATE sesiones
       SET fin = ?, duracion_segundos = MAX(0, ? - inicio), motivo_cierre = 'revocado'
       WHERE codigo = ? AND fin IS NULL`,
    ).bind(ahora, ahora, codigo),
  ]);
  const duraciones = (abiertas.results || []).map((fila) =>
    textoDuracion(Math.max(0, ahora - Number(fila.inicio))),
  );
  const extra = duraciones.length
    ? `Había una sesión abierta (${duraciones.join(", ")}). Si el programa sigue abierto, se bloqueará en el próximo latido.`
    : "Si lo está usando, se bloqueará en el próximo latido.";
  return `Código de ${persona.nombre} revocado. ${extra}`;
}

async function activos(env: Env, ahora: number): Promise<string> {
  const limite = ahora - enteroActiva(env);
  await env.DB.prepare(
    `UPDATE sesiones
     SET fin = ultimo_latido,
         duracion_segundos = MAX(0, ultimo_latido - inicio),
         motivo_cierre = 'sin_latido'
     WHERE fin IS NULL AND ultimo_latido < ?`,
  )
    .bind(limite)
    .run();
  const filas = await env.DB.prepare(
    `SELECT s.*, p.nombre AS nombre
     FROM sesiones s
     JOIN personas p ON p.codigo = s.codigo
     WHERE s.fin IS NULL
     ORDER BY s.inicio DESC
     LIMIT 40`,
  ).all<Sesion & { nombre: string }>();
  const sesiones = filas.results || [];
  if (!sesiones.length) return "Ahora mismo nadie está usando Drako Cam.";
  const lineas = sesiones.map((sesion) => {
    const minutos = Math.max(0, Math.floor((ahora - sesion.inicio) / 60));
    return `• ${sesion.nombre} — ${textoOficina(sesion.oficina)} — ${sesion.equipo} — ${textoLugar(sesion.ciudad, sesion.pais)} — desde ${formatearHora(sesion.inicio)} — hace ${minutos} min`;
  });
  return [`En uso ahora (${sesiones.length}):`, ...lineas].join("\n");
}

function enteroActiva(env: Env): number {
  const numero = Number(env.SESION_ACTIVA_SECS);
  if (!Number.isFinite(numero)) return 180;
  return Math.min(3600, Math.max(60, Math.floor(numero)));
}

async function historial(env: Env, argumento: string): Promise<string> {
  const codigo = normalizarCodigo(argumento);
  if (!codigo) return "Escribe el código.\nEjemplo: /historial DRAKO-XXXX-XXXX-XXXX-XXXX";
  const persona = await env.DB.prepare("SELECT * FROM personas WHERE codigo = ?")
    .bind(codigo)
    .first<Persona>();
  if (!persona) return "No existe ese código.";
  const filas = await env.DB.prepare(
    "SELECT * FROM sesiones WHERE codigo = ? ORDER BY inicio DESC LIMIT 15",
  )
    .bind(codigo)
    .all<Sesion>();
  const sesiones = filas.results || [];
  const cabecera = `Historial de ${persona.nombre}, oficina ${textoOficina(persona.oficina)} (${codigo}):`;
  if (!sesiones.length) return `${cabecera}\nTodavía no hay sesiones.`;
  const lineas = sesiones.map((sesion) => {
    const lugar = textoLugar(sesion.ciudad, sesion.pais);
    const ip = sesion.ip ? ` — ${sesion.ip}` : "";
    const oficina = textoOficina(sesion.oficina || persona.oficina);
    if (sesion.fin == null) {
      return `• ${formatearHora(sesion.inicio)} — en curso — ${sesion.equipo} — ${oficina} — ${lugar}${ip}`;
    }
    const duracion = textoDuracion(sesion.duracion_segundos ?? Math.max(0, sesion.fin - sesion.inicio));
    const motivo = sesion.motivo_cierre === "sin_latido" ? " — se quedó sin latido" : "";
    return `• ${formatearHora(sesion.inicio)} — ${duracion} — ${sesion.equipo} — ${oficina} — ${lugar}${ip}${motivo}`;
  });
  return [cabecera, ...lineas].join("\n");
}

async function vistaPendientes(env: Env): Promise<RespuestaBot> {
  const filas = await env.DB.prepare(
    `SELECT id, nombre, oficina, equipo, ciudad, pais, creada_en
     FROM solicitudes WHERE estado = 'pendiente'
     ORDER BY creada_en DESC LIMIT 8`,
  ).all<{
    id: string;
    nombre: string;
    oficina: string;
    equipo: string;
    ciudad: string;
    pais: string;
    creada_en: number;
  }>();
  const lista = filas.results || [];
  if (!lista.length) return conMenu("No hay solicitudes pendientes.");
  const lineas = lista.map((fila) =>
    `• ${fila.nombre} — ${textoOficina(fila.oficina)} — ${fila.equipo} — ${textoLugar(fila.ciudad, fila.pais)} — ${formatearHora(fila.creada_en)}`,
  );
  const teclas = lista.map((fila) => [
    { text: "Aprobar", callback_data: `aprobar:${fila.id}` },
    { text: "Rechazar", callback_data: `rechazar:${fila.id}` },
  ]);
  return plano(
    [`Solicitudes pendientes (${lista.length}):`, ...lineas].join("\n"),
    { reply_markup: { inline_keyboard: teclas } },
  );
}

async function borrar(env: Env, argumento: string): Promise<string> {
  const codigo = normalizarCodigo(argumento);
  if (!codigo) return "Escribe el código.\nEjemplo: /borrar DRAKO-XXXX-XXXX-XXXX-XXXX";
  const persona = await env.DB.prepare("SELECT * FROM personas WHERE codigo = ?")
    .bind(codigo)
    .first<Persona>();
  if (!persona) return "No existe ese código.";
  await env.DB.batch([
    env.DB.prepare("DELETE FROM sesiones WHERE codigo = ?").bind(codigo),
    env.DB.prepare("DELETE FROM intentos WHERE codigo = ?").bind(codigo),
    env.DB.prepare("DELETE FROM personas WHERE codigo = ?").bind(codigo),
  ]);
  return `Se eliminó a ${persona.nombre} y su historial. El código ya no sirve.`;
}
