import { prepararFirmante } from "./crypto";
import { leerLugar } from "./lugar";
import { atenderLicencia } from "./licencia";
import { atenderSolicitud } from "./solicitud";
import { atenderComandos, atenderWebhook } from "./telegram";
import type { Env } from "./tipos";

function json(datos: unknown, estado = 200): Response {
  return new Response(JSON.stringify(datos), {
    status: estado,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

const RUTAS = {
  "/v1/activar": "activar",
  "/v1/latido": "latido",
  "/v1/cerrar": "cerrar",
  "/v1/estado": "estado",
} as const;

export async function atender(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const url = new URL(request.url);
  try {
    if (request.method === "GET" && url.pathname === "/v1/salud") {
      return json({ ok: true, servicio: "drako-cam-licencias" });
    }
    if (url.pathname === "/telegram/webhook") {
      if (request.method !== "POST") return json({ error: "metodo" }, 405);
      const lugar = leerLugar(request, env);
      return await atenderWebhook(request, env, lugar.ahora);
    }
    if (url.pathname === "/telegram/comandos") {
      if (request.method !== "POST") return json({ error: "metodo" }, 405);
      return await atenderComandos(request, env);
    }
    if (url.pathname === "/v1/solicitud") {
      if (request.method !== "POST") return json({ error: "metodo" }, 405);
      const firmante = await prepararFirmante(env.SIGNING_SEED);
      const lugar = leerLugar(request, env);
      return await atenderSolicitud(request, env, ctx, firmante, lugar);
    }
    const accion = RUTAS[url.pathname as keyof typeof RUTAS];
    if (!accion) return json({ error: "ruta" }, 404);
    if (request.method !== "POST") return json({ error: "metodo" }, 405);
    const firmante = await prepararFirmante(env.SIGNING_SEED);
    const lugar = leerLugar(request, env);
    return await atenderLicencia(request, env, ctx, firmante, accion, lugar);
  } catch (error) {
    console.error("Fallo interno", error instanceof Error ? error.name : "error");
    return json({ error: "servidor" }, 500);
  }
}

export default {
  fetch: atender,
};
