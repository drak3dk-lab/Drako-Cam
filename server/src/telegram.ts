import { enviarTelegram, formatearHora, textoDuracion, textoLugar, textoOficina } from "./avisos";
import { generarCodigo, iguales, limpiarNombre, normalizarCodigo } from "./crypto";
import { contestarCallback } from "./solicitud";
import type { Env, Persona, Sesion } from "./tipos";

const AYUDA = [
  "Comandos de Drako Cam:",
  "/nuevo <nombre> — crea un código para una persona",
  "/lista — códigos y si están activos",
  "/revocar <código> — impide que vuelva a entrar",
  "/activos — quién lo está usando ahora",
  "/historial <código> — últimas sesiones",
  "/pendientes — solicitudes que aún no has decidido",
  "/borrar <código> — elimina a la persona y su historial",
  "/ayuda — esta lista",
].join("\n");

function jsonVacio(): Response {
  return new Response("", { status: 200 });
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
    if (!esAdmin) {
      return jsonVacio();
    }
    await contestarCallback(
      env,
      {
        id: consulta.id,
        data: typeof consulta.data === "string" ? consulta.data : "",
        chatId: String(chatId),
        messageId: typeof consulta.message?.message_id === "number" ? consulta.message.message_id : null,
      },
      ahora,
    );
    return jsonVacio();
  }
  const mensaje = update.message;
  const texto = typeof mensaje?.text === "string" ? mensaje.text.trim() : "";
  const chatId = mensaje?.chat?.id;
  if (!texto || chatId === undefined || chatId === null) return jsonVacio();
  if (!iguales(String(chatId), chatAdmin)) return jsonVacio();
  const respuesta = await orden(env, texto, ahora);
  await enviarTelegram(env, respuesta);
  return jsonVacio();
}

async function orden(env: Env, texto: string, ahora: number): Promise<string> {
  const coincidencia = texto.match(/^\/([a-z]+)(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]+))?$/i);
  if (!coincidencia) return "No entiendo ese mensaje.\n\n" + AYUDA;
  const comando = coincidencia[1].toLowerCase();
  const argumento = (coincidencia[2] || "").trim();
  if (comando === "ayuda" || comando === "start" || comando === "help") return AYUDA;
  if (comando === "nuevo") return crear(env, argumento, ahora);
  if (comando === "lista") return listar(env);
  if (comando === "revocar") return revocar(env, argumento, ahora);
  if (comando === "activos") return activos(env, ahora);
  if (comando === "historial") return historial(env, argumento);
  if (comando === "pendientes") return pendientes(env);
  if (comando === "borrar") return borrar(env, argumento);
  return "Ese comando no existe.\n\n" + AYUDA;
}

async function crear(env: Env, argumento: string, ahora: number): Promise<string> {
  const nombre = limpiarNombre(argumento);
  if (!nombre) return "Escribe el nombre de la persona.\nEjemplo: /nuevo Ana García";
  for (let intento = 0; intento < 5; intento += 1) {
    const codigo = generarCodigo();
    try {
      await env.DB.prepare(
        "INSERT INTO personas (codigo, nombre, creado_en) VALUES (?, ?, ?)",
      )
        .bind(codigo, nombre, ahora)
        .run();
      return [
        `Código creado para ${nombre}:`,
        codigo,
        "Dáselo a esa persona. Queda ligado al primer equipo que lo active.",
      ].join("\n");
    } catch {
      // Choque muy raro de código: se prueba otro.
    }
  }
  return "No se pudo crear el código. Prueba otra vez.";
}

async function listar(env: Env): Promise<string> {
  const filas = await env.DB.prepare(
    "SELECT codigo, nombre, oficina, revocado_en, huella, equipo FROM personas ORDER BY creado_en DESC LIMIT 40",
  ).all<Persona>();
  const personas = filas.results || [];
  if (!personas.length) return "Todavía no hay códigos. Crea uno con /nuevo <nombre>.";
  const lineas = personas.map((persona) => {
    const estado = persona.revocado_en ? "revocado" : "activo";
    const equipo = persona.equipo ? ` — ${persona.equipo}` : " — sin equipo";
    const oficina = ` — ${textoOficina(persona.oficina)}`;
    return `• ${persona.nombre} — ${persona.codigo} — ${estado}${oficina}${persona.revocado_en ? "" : equipo}`;
  });
  return [`Códigos (${personas.length}):`, ...lineas].join("\n");
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

async function pendientes(env: Env): Promise<string> {
  const filas = await env.DB.prepare(
    `SELECT nombre, oficina, equipo, ciudad, pais, creada_en
     FROM solicitudes WHERE estado = 'pendiente'
     ORDER BY creada_en DESC LIMIT 40`,
  ).all<{
    nombre: string;
    oficina: string;
    equipo: string;
    ciudad: string;
    pais: string;
    creada_en: number;
  }>();
  const lista = filas.results || [];
  if (!lista.length) return "No hay solicitudes pendientes.";
  const lineas = lista.map((fila) =>
    `• ${fila.nombre} — ${textoOficina(fila.oficina)} — ${fila.equipo} — ${textoLugar(fila.ciudad, fila.pais)} — ${formatearHora(fila.creada_en)}`,
  );
  return [`Solicitudes pendientes (${lista.length}):`, ...lineas].join("\n");
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
