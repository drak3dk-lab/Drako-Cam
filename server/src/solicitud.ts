import { enviarTelegram, formatearHora, llamarTelegram, textoLugar, textoOficina } from "./avisos";
import {
  entero,
  firmarCarga,
  generarCodigo,
  limpiarNombre,
  limpiarTexto,
  normalizarHuella,
} from "./crypto";
import type { Carga, Env, Firmante, Lugar, Solicitud } from "./tipos";

const MENSAJES: Record<string, string> = {
  enviada: "Solicitud enviada. El administrador te pasará el código si la aprueba.",
  ya_pendiente: "Ya hay una solicitud pendiente para este equipo.",
  ya_aprobada: "Este equipo ya tiene un código aprobado. Pídeselo al administrador.",
  limitada: "Demasiadas solicitudes desde esta red. Espera un rato.",
  mal_formato: "Faltan el nombre, la oficina o la huella del equipo.",
};

function limiteSolicitudes(env: Env): number {
  return entero(env.LIMITE_SOLICITUDES, 5, 1, 100);
}

function json(datos: unknown, estado = 200): Response {
  return new Response(JSON.stringify(datos), {
    status: estado,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

async function responder(env: Env, firmante: Firmante, lugar: Lugar, campos: Partial<Carga> & Pick<Carga, "ok" | "motivo" | "estado">): Promise<Response> {
  const latido = entero(env.LATIDO_SEGUNDOS, 60, 15, 600);
  const carga: Carga = {
    v: 1,
    accion: "solicitud",
    ok: campos.ok,
    motivo: campos.motivo,
    mensaje: campos.mensaje || MENSAJES[campos.motivo] || "",
    persona: campos.persona || "",
    codigo_hash: "",
    huella: campos.huella || "",
    sesion: campos.sesion || "",
    estado: campos.estado,
    emitido: lugar.ahora,
    expira: lugar.ahora + Math.max(latido * 3, 180),
    latido_segundos: latido,
    gracia_horas: entero(env.GRACIA_HORAS, 24, 0, 168),
  };
  const firma = await firmarCarga(firmante, carga);
  return json({ carga, firma });
}

async function demasiadas(env: Env, lugar: Lugar): Promise<boolean> {
  if (!lugar.ip) return false;
  const fila = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM solicitudes WHERE ip = ? AND creada_en > ?",
  )
    .bind(lugar.ip, lugar.ahora - 3600)
    .first<{ n: number }>();
  return Number(fila?.n || 0) >= limiteSolicitudes(env);
}

export function textoSolicitud(datos: {
  nombre: string;
  oficina: string;
  equipo: string;
  ciudad: string;
  pais: string;
  ip: string;
  ahora: number;
}): string {
  return [
    "Drako Cam — solicitud de acceso",
    `Persona: ${datos.nombre}`,
    `Oficina: ${textoOficina(datos.oficina)}`,
    `Equipo: ${datos.equipo}`,
    `Lugar: ${textoLugar(datos.ciudad, datos.pais)}`,
    `IP: ${datos.ip || "no disponible"}`,
    `Hora: ${formatearHora(datos.ahora)}`,
    "Aprueba para crear el código de este PC, o rechaza para cerrar la solicitud.",
  ].join("\n");
}

function teclado(id: string): Record<string, unknown> {
  return {
    inline_keyboard: [[
      { text: "Aprobar", callback_data: `aprobar:${id}` },
      { text: "Rechazar", callback_data: `rechazar:${id}` },
    ]],
  };
}

export async function atenderSolicitud(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
): Promise<Response> {
  let cuerpo: Record<string, unknown> | null = null;
  try {
    const texto = await request.text();
    if (texto.length <= 8192) {
      const datos = JSON.parse(texto) as unknown;
      if (datos && typeof datos === "object" && !Array.isArray(datos)) {
        cuerpo = datos as Record<string, unknown>;
      }
    }
  } catch {
    cuerpo = null;
  }
  if (!cuerpo) return json({ error: "json" }, 400);
  const nombre = limpiarNombre(cuerpo.nombre);
  const oficina = limpiarNombre(cuerpo.oficina);
  const huella = normalizarHuella(cuerpo.huella);
  const equipo = limpiarTexto(cuerpo.equipo, 80) || "equipo-desconocido";
  if (!nombre || !oficina || !huella) {
    return responder(env, firmante, lugar, {
      ok: false,
      motivo: "mal_formato",
      estado: "mal_formato",
      huella: huella || "",
      persona: nombre || "",
      mensaje: MENSAJES.mal_formato,
    });
  }
  const yaCodigo = await env.DB.prepare(
    "SELECT codigo FROM personas WHERE huella = ? AND revocado_en IS NULL LIMIT 1",
  )
    .bind(huella)
    .first<{ codigo: string }>();
  if (yaCodigo) {
    return responder(env, firmante, lugar, {
      ok: true,
      motivo: "ya_aprobada",
      estado: "aprobada",
      huella,
      persona: nombre,
      mensaje: MENSAJES.ya_aprobada,
    });
  }
  const pendiente = await env.DB.prepare(
    "SELECT id FROM solicitudes WHERE huella = ? AND estado = 'pendiente' LIMIT 1",
  )
    .bind(huella)
    .first<{ id: string }>();
  if (pendiente) {
    return responder(env, firmante, lugar, {
      ok: true,
      motivo: "ya_pendiente",
      estado: "pendiente",
      huella,
      persona: nombre,
      sesion: pendiente.id,
      mensaje: MENSAJES.ya_pendiente,
    });
  }
  if (await demasiadas(env, lugar)) {
    return responder(env, firmante, lugar, {
      ok: false,
      motivo: "limitada",
      estado: "limitada",
      huella,
      persona: nombre,
      mensaje: MENSAJES.limitada,
    });
  }
  const id = crypto.randomUUID();
  await env.DB.prepare(
    `INSERT INTO solicitudes
      (id, nombre, oficina, equipo, huella, ip, pais, ciudad, creada_en, estado)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')`,
  )
    .bind(id, nombre, oficina, equipo, huella, lugar.ip, lugar.pais, lugar.ciudad, lugar.ahora)
    .run();
  const aviso = textoSolicitud({
    nombre,
    oficina,
    equipo,
    ciudad: lugar.ciudad,
    pais: lugar.pais,
    ip: lugar.ip,
    ahora: lugar.ahora,
  });
  ctx.waitUntil(enviarTelegram(env, aviso, { reply_markup: teclado(id) }));
  return responder(env, firmante, lugar, {
    ok: true,
    motivo: "enviada",
    estado: "pendiente",
    huella,
    persona: nombre,
    sesion: id,
    mensaje: MENSAJES.enviada,
  });
}

export async function decidirSolicitud(
  env: Env,
  id: string,
  aprobar: boolean,
  ahora: number,
): Promise<{ aviso: string; codigo: string }> {
  const solicitud = await env.DB.prepare("SELECT * FROM solicitudes WHERE id = ?")
    .bind(id)
    .first<Solicitud>();
  if (!solicitud) return { aviso: "No existe esa solicitud.", codigo: "" };
  if (solicitud.estado !== "pendiente") {
    return { aviso: `La solicitud de ${solicitud.nombre} ya estaba ${solicitud.estado}.`, codigo: "" };
  }
  const marca = await env.DB.prepare(
    "UPDATE solicitudes SET estado = 'aprobando' WHERE id = ? AND estado = 'pendiente'",
  )
    .bind(id)
    .run();
  if (!marca.meta.changes) {
    return { aviso: `La solicitud de ${solicitud.nombre} ya no está pendiente.`, codigo: "" };
  }
  if (!aprobar) {
    await env.DB.prepare(
      "UPDATE solicitudes SET estado = 'rechazada', cerrada_en = ? WHERE id = ?",
    )
      .bind(ahora, id)
      .run();
    return {
      aviso: `Solicitud rechazada: ${solicitud.nombre}, oficina ${textoOficina(solicitud.oficina)}.`,
      codigo: "",
    };
  }
  for (let intento = 0; intento < 5; intento += 1) {
    const codigo = generarCodigo();
    try {
      await env.DB.batch([
        env.DB.prepare(
          `INSERT INTO personas (codigo, nombre, oficina, creado_en, huella, equipo)
           VALUES (?, ?, ?, ?, ?, ?)`,
        ).bind(codigo, solicitud.nombre, solicitud.oficina, ahora, solicitud.huella, solicitud.equipo),
        env.DB.prepare(
          "UPDATE solicitudes SET estado = 'aprobada', codigo = ?, cerrada_en = ? WHERE id = ?",
        ).bind(codigo, ahora, id),
      ]);
      return {
        aviso: [
          `Código para ${solicitud.nombre}:`,
          codigo,
          `Oficina: ${textoOficina(solicitud.oficina)}`,
          `Equipo: ${solicitud.equipo}`,
          "Está ligado a ese PC. Pásaselo tú a esa persona. No se envía a nadie más.",
        ].join("\n"),
        codigo,
      };
    } catch {
      // Choque de código: se prueba otro.
    }
  }
  await env.DB.prepare("UPDATE solicitudes SET estado = 'pendiente' WHERE id = ? AND estado = 'aprobando'")
    .bind(id)
    .run();
  return { aviso: "No se pudo crear el código. La solicitud sigue pendiente.", codigo: "" };
}

export async function contestarCallback(
  env: Env,
  datos: {
    id: string;
    data: string;
    chatId: string;
    messageId: number | null;
  },
  ahora: number,
): Promise<void> {
  await llamarTelegram(env, "answerCallbackQuery", { callback_query_id: datos.id });
  const coincidencia = datos.data.match(/^(aprobar|rechazar):([0-9a-f-]{36})$/i);
  if (!coincidencia) return;
  const decision = await decidirSolicitud(env, coincidencia[2], coincidencia[1].toLowerCase() === "aprobar", ahora);
  if (datos.messageId !== null) {
    const resumen = decision.codigo
      ? "Solicitud aprobada. El código va en el siguiente mensaje, solo para ti."
      : decision.aviso;
    await llamarTelegram(env, "editMessageText", {
      chat_id: datos.chatId,
      message_id: datos.messageId,
      text: resumen.slice(0, 4000),
    });
  }
  if (decision.codigo) {
    await enviarTelegram(env, decision.aviso);
  } else if (datos.messageId === null) {
    await enviarTelegram(env, decision.aviso);
  }
}
