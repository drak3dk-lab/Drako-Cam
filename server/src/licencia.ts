import { dejarAviso, textoCierre, textoCorte, textoInicio, textoRechazo } from "./avisos";
import {
  entero,
  firmarCarga,
  limpiarTexto,
  normalizarCodigo,
  normalizarHuella,
  sha256Hex,
} from "./crypto";
import type { Carga, Env, Firmante, Lugar, Persona, Sesion } from "./tipos";

const MENSAJES: Record<string, string> = {
  ok_activar: "Acceso concedido.",
  ok_estado: "El código sigue activo.",
  ok_latido: "Sesión en curso.",
  ok_cerrar: "Sesión cerrada.",
  ya_cerrada: "La sesión ya estaba cerrada.",
  revocado: "Este código está revocado.",
  desconocido: "Este código no existe.",
  otro_equipo: "Este código está ligado a otro equipo.",
  mal_formato: "El código o la huella del equipo no son válidos.",
  sesion_desconocida: "No hay una sesión abierta. Hay que volver a entrar.",
  sesion_ajena: "Esa sesión no corresponde a este código.",
  limitada: "Demasiados intentos. Espera un rato.",
  sin_vincular: "El código todavía no está ligado a un equipo.",
};

function segundosLatido(env: Env): number {
  return entero(env.LATIDO_SEGUNDOS, 60, 15, 600);
}

function segundosActiva(env: Env): number {
  return entero(env.SESION_ACTIVA_SECS, 180, 60, 3600);
}

function horasGracia(env: Env): number {
  return entero(env.GRACIA_HORAS, 24, 0, 168);
}

function limiteIntentos(env: Env): number {
  return entero(env.LIMITE_INTENTOS, 30, 1, 1000);
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

async function cargaBase(
  env: Env,
  lugar: Lugar,
  campos: Partial<Carga> & Pick<Carga, "accion" | "ok" | "motivo" | "estado">,
): Promise<Carga> {
  const latido = segundosLatido(env);
  return {
    v: 1,
    accion: campos.accion,
    ok: campos.ok,
    motivo: campos.motivo,
    mensaje: campos.mensaje || MENSAJES[campos.motivo] || "",
    persona: campos.persona || "",
    codigo_hash: campos.codigo_hash || "",
    huella: campos.huella || "",
    sesion: campos.sesion || "",
    estado: campos.estado,
    emitido: lugar.ahora,
    expira: lugar.ahora + Math.max(latido * 3, 180),
    latido_segundos: latido,
    gracia_horas: horasGracia(env),
  };
}

async function responder(firmante: Firmante, carga: Carga): Promise<Response> {
  const firma = await firmarCarga(firmante, carga);
  return json({ carga, firma });
}

async function leerCuerpo(request: Request): Promise<Record<string, unknown> | null> {
  const texto = await request.text();
  if (texto.length > 8192) return null;
  try {
    const datos = JSON.parse(texto) as unknown;
    if (!datos || typeof datos !== "object" || Array.isArray(datos)) return null;
    return datos as Record<string, unknown>;
  } catch {
    return null;
  }
}

async function cerrarInactivas(env: Env, ahora: number): Promise<void> {
  const limite = ahora - segundosActiva(env);
  await env.DB.prepare(
    `UPDATE sesiones
     SET fin = ultimo_latido,
         duracion_segundos = MAX(0, ultimo_latido - inicio),
         motivo_cierre = 'sin_latido'
     WHERE fin IS NULL AND ultimo_latido < ?`,
  )
    .bind(limite)
    .run();
}

async function demasiados(env: Env, lugar: Lugar): Promise<boolean> {
  if (!lugar.ip) return false;
  const fila = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM intentos WHERE ip = ? AND momento > ?",
  )
    .bind(lugar.ip, lugar.ahora - 3600)
    .first<{ n: number }>();
  return Number(fila?.n || 0) >= limiteIntentos(env);
}

async function anotarIntento(
  env: Env,
  lugar: Lugar,
  codigo: string,
  motivo: string,
  equipo: string,
  huella: string,
): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO intentos (codigo, motivo, equipo, huella, ip, pais, ciudad, momento)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(codigo, motivo, equipo, huella, lugar.ip, lugar.pais, lugar.ciudad, lugar.ahora)
    .run();
}

function rechazar(
  ctx: ExecutionContext,
  env: Env,
  lugar: Lugar,
  motivo: string,
  codigo: string,
  equipo: string,
  huella: string,
): void {
  dejarAviso(
    ctx,
    env,
    textoRechazo({
      motivo,
      codigo,
      equipo,
      ciudad: lugar.ciudad,
      pais: lugar.pais,
      ip: lugar.ip,
      ahora: lugar.ahora,
    }),
  );
  ctx.waitUntil(anotarIntento(env, lugar, codigo, motivo, equipo, huella));
}

async function buscarPersona(env: Env, codigo: string): Promise<Persona | null> {
  return env.DB.prepare("SELECT * FROM personas WHERE codigo = ?").bind(codigo).first<Persona>();
}

export async function atenderLicencia(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  accion: "activar" | "latido" | "cerrar" | "estado",
  lugar: Lugar,
): Promise<Response> {
  const cuerpo = await leerCuerpo(request);
  if (!cuerpo) return json({ error: "json" }, 400);
  const codigo = normalizarCodigo(cuerpo.codigo);
  const huella = normalizarHuella(cuerpo.huella);
  const equipo = limpiarTexto(cuerpo.equipo, 80) || "equipo-desconocido";
  const sesionId = limpiarTexto(cuerpo.sesion, 64);
  const codigoHash = codigo ? await sha256Hex(codigo) : "";

  if (!codigo || !huella) {
    const carga = await cargaBase(env, lugar, {
      accion,
      ok: false,
      motivo: "mal_formato",
      estado: "mal_formato",
      codigo_hash: codigoHash,
      huella: huella || "",
      mensaje: MENSAJES.mal_formato,
    });
    return responder(firmante, carga);
  }

  await cerrarInactivas(env, lugar.ahora);
  if (await demasiados(env, lugar)) {
    const carga = await cargaBase(env, lugar, {
      accion,
      ok: false,
      motivo: "limitada",
      estado: "limitada",
      codigo_hash: codigoHash,
      huella,
      mensaje: MENSAJES.limitada,
    });
    return responder(firmante, carga);
  }

  if (accion === "cerrar") {
    return cerrar(env, ctx, firmante, lugar, codigo, codigoHash, huella, equipo, sesionId);
  }
  if (accion === "latido") {
    return latido(env, ctx, firmante, lugar, codigo, codigoHash, huella, equipo, sesionId);
  }
  if (accion === "estado") {
    return estado(env, ctx, firmante, lugar, codigo, codigoHash, huella, equipo);
  }
  return activar(env, ctx, firmante, lugar, codigo, codigoHash, huella, equipo);
}

async function denegar(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  accion: string,
  motivo: "revocado" | "desconocido" | "otro_equipo",
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
  persona: string,
): Promise<Response> {
  rechazar(ctx, env, lugar, motivo, codigo, equipo, huella);
  const carga = await cargaBase(env, lugar, {
    accion,
    ok: false,
    motivo,
    estado: motivo === "otro_equipo" ? "otro_equipo" : motivo === "revocado" ? "revocada" : "desconocida",
    codigo_hash: codigoHash,
    huella,
    persona,
    mensaje: MENSAJES[motivo],
  });
  return responder(firmante, carga);
}

async function comprobarPersona(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  accion: string,
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
): Promise<{ persona: Persona; respuesta?: Response }> {
  const persona = await buscarPersona(env, codigo);
  if (!persona) {
    return {
      persona: {
        codigo,
        nombre: "",
        creado_en: 0,
        revocado_en: null,
        huella: null,
        equipo: null,
      },
      respuesta: await denegar(
        env, ctx, firmante, lugar, accion, "desconocido", codigo, codigoHash, huella, equipo, "",
      ),
    };
  }
  if (persona.revocado_en) {
    return {
      persona,
      respuesta: await denegar(
        env, ctx, firmante, lugar, accion, "revocado", codigo, codigoHash, huella, equipo, persona.nombre,
      ),
    };
  }
  if (persona.huella && persona.huella !== huella) {
    return {
      persona,
      respuesta: await denegar(
        env, ctx, firmante, lugar, accion, "otro_equipo", codigo, codigoHash, huella, equipo, persona.nombre,
      ),
    };
  }
  return { persona };
}

async function activar(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
): Promise<Response> {
  const visto = await comprobarPersona(
    env, ctx, firmante, lugar, "activar", codigo, codigoHash, huella, equipo,
  );
  if (visto.respuesta) return visto.respuesta;
  const persona = visto.persona;
  const id = crypto.randomUUID();
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE personas SET huella = ?, equipo = ? WHERE codigo = ?",
    ).bind(huella, equipo, codigo),
    env.DB.prepare(
      `UPDATE sesiones
       SET fin = ?, duracion_segundos = MAX(0, ? - inicio), motivo_cierre = 'nueva_sesion'
       WHERE codigo = ? AND fin IS NULL`,
    ).bind(lugar.ahora, lugar.ahora, codigo),
    env.DB.prepare(
      `INSERT INTO sesiones
        (id, codigo, nombre, equipo, huella, ip, pais, ciudad, inicio, ultimo_latido)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(
      id, codigo, persona.nombre, equipo, huella, lugar.ip, lugar.pais, lugar.ciudad, lugar.ahora, lugar.ahora,
    ),
  ]);
  dejarAviso(
    ctx,
    env,
    textoInicio({
      persona: persona.nombre,
      equipo,
      ciudad: lugar.ciudad,
      pais: lugar.pais,
      ip: lugar.ip,
      ahora: lugar.ahora,
    }),
  );
  const carga = await cargaBase(env, lugar, {
    accion: "activar",
    ok: true,
    motivo: "ok",
    estado: "activa",
    codigo_hash: codigoHash,
    huella,
    persona: persona.nombre,
    sesion: id,
    mensaje: MENSAJES.ok_activar,
  });
  return responder(firmante, carga);
}

async function estado(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
): Promise<Response> {
  const visto = await comprobarPersona(
    env, ctx, firmante, lugar, "estado", codigo, codigoHash, huella, equipo,
  );
  if (visto.respuesta) return visto.respuesta;
  const sinVincular = !visto.persona.huella;
  const carga = await cargaBase(env, lugar, {
    accion: "estado",
    ok: true,
    motivo: sinVincular ? "sin_vincular" : "ok",
    estado: sinVincular ? "sin_vincular" : "activa",
    codigo_hash: codigoHash,
    huella,
    persona: visto.persona.nombre,
    mensaje: sinVincular ? MENSAJES.sin_vincular : MENSAJES.ok_estado,
  });
  return responder(firmante, carga);
}

async function latido(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
  sesionId: string,
): Promise<Response> {
  const persona = await buscarPersona(env, codigo);
  if (!persona) {
    return denegar(
      env, ctx, firmante, lugar, "latido", "desconocido", codigo, codigoHash, huella, equipo, "",
    );
  }
  if (persona.revocado_en) {
    const abierta = sesionId
      ? await env.DB.prepare("SELECT * FROM sesiones WHERE id = ?").bind(sesionId).first<Sesion>()
      : null;
    if (abierta && abierta.codigo === codigo && abierta.fin == null) {
      const duracion = Math.max(0, lugar.ahora - abierta.inicio);
      await env.DB.prepare(
        `UPDATE sesiones
         SET fin = ?, duracion_segundos = ?, motivo_cierre = 'revocado'
         WHERE id = ? AND fin IS NULL`,
      )
        .bind(lugar.ahora, duracion, sesionId)
        .run();
      dejarAviso(
        ctx,
        env,
        textoCorte({
          persona: persona.nombre,
          equipo: abierta.equipo,
          duracion,
          ahora: lugar.ahora,
        }),
      );
    } else {
      rechazar(ctx, env, lugar, "revocado", codigo, equipo, huella);
    }
    const carga = await cargaBase(env, lugar, {
      accion: "latido",
      ok: false,
      motivo: "revocado",
      estado: "revocada",
      codigo_hash: codigoHash,
      huella,
      persona: persona.nombre,
      sesion: sesionId,
      mensaje: MENSAJES.revocado,
    });
    return responder(firmante, carga);
  }
  if (persona.huella && persona.huella !== huella) {
    return denegar(
      env, ctx, firmante, lugar, "latido", "otro_equipo", codigo, codigoHash, huella, equipo, persona.nombre,
    );
  }
  const sesion = sesionId
    ? await env.DB.prepare("SELECT * FROM sesiones WHERE id = ?").bind(sesionId).first<Sesion>()
    : null;
  if (!sesion || sesion.codigo !== codigo || sesion.huella !== huella || sesion.fin != null) {
    const carga = await cargaBase(env, lugar, {
      accion: "latido",
      ok: false,
      motivo: "sesion_desconocida",
      estado: "activa",
      codigo_hash: codigoHash,
      huella,
      persona: persona.nombre,
      mensaje: MENSAJES.sesion_desconocida,
    });
    return responder(firmante, carga);
  }
  await env.DB.prepare(
    `UPDATE sesiones
     SET ultimo_latido = ?, equipo = ?, ip = ?, pais = ?, ciudad = ?
     WHERE id = ?`,
  )
    .bind(lugar.ahora, equipo, lugar.ip, lugar.pais, lugar.ciudad, sesionId)
    .run();
  const carga = await cargaBase(env, lugar, {
    accion: "latido",
    ok: true,
    motivo: "ok",
    estado: "activa",
    codigo_hash: codigoHash,
    huella,
    persona: persona.nombre,
    sesion: sesionId,
    mensaje: MENSAJES.ok_latido,
  });
  return responder(firmante, carga);
}

async function cerrar(
  env: Env,
  ctx: ExecutionContext,
  firmante: Firmante,
  lugar: Lugar,
  codigo: string,
  codigoHash: string,
  huella: string,
  equipo: string,
  sesionId: string,
): Promise<Response> {
  const persona = await buscarPersona(env, codigo);
  if (!persona || (persona.huella && persona.huella !== huella)) {
    const motivo = !persona ? "desconocido" : "otro_equipo";
    return denegar(
      env, ctx, firmante, lugar, "cerrar", motivo, codigo, codigoHash, huella, equipo, persona?.nombre || "",
    );
  }
  const sesion = sesionId
    ? await env.DB.prepare("SELECT * FROM sesiones WHERE id = ?").bind(sesionId).first<Sesion>()
    : null;
  if (!sesion || sesion.codigo !== codigo || sesion.huella !== huella) {
    const carga = await cargaBase(env, lugar, {
      accion: "cerrar",
      ok: false,
      motivo: "sesion_ajena",
      estado: "desconocida",
      codigo_hash: codigoHash,
      huella,
      persona: persona.nombre,
      mensaje: MENSAJES.sesion_ajena,
    });
    return responder(firmante, carga);
  }
  if (sesion.fin != null) {
    const carga = await cargaBase(env, lugar, {
      accion: "cerrar",
      ok: true,
      motivo: "ya_cerrada",
      estado: "cerrada",
      codigo_hash: codigoHash,
      huella,
      persona: persona.nombre,
      sesion: sesion.id,
      mensaje: MENSAJES.ya_cerrada,
    });
    return responder(firmante, carga);
  }
  const duracion = Math.max(0, lugar.ahora - sesion.inicio);
  await env.DB.prepare(
    `UPDATE sesiones
     SET fin = ?, duracion_segundos = ?, motivo_cierre = 'cierre', ultimo_latido = ?
     WHERE id = ? AND fin IS NULL`,
  )
    .bind(lugar.ahora, duracion, lugar.ahora, sesion.id)
    .run();
  dejarAviso(
    ctx,
    env,
    textoCierre({ persona: persona.nombre, equipo: equipo || sesion.equipo, duracion, ahora: lugar.ahora }),
  );
  const carga = await cargaBase(env, lugar, {
    accion: "cerrar",
    ok: true,
    motivo: "ok",
    estado: "cerrada",
    codigo_hash: codigoHash,
    huella,
    persona: persona.nombre,
    sesion: sesion.id,
    mensaje: MENSAJES.ok_cerrar,
  });
  return responder(firmante, carga);
}
