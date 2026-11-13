import type { Env, Lugar } from "./tipos";

export function leerLugar(request: Request, env: Pick<Env, "MODO_PRUEBA">): Lugar {
  const cf = (request.cf ?? {}) as { country?: unknown; city?: unknown };
  let pais = typeof cf.country === "string" ? cf.country : "";
  let ciudad = typeof cf.city === "string" ? cf.city : "";
  let ip = request.headers.get("CF-Connecting-IP") || "";
  let ahora = Math.floor(Date.now() / 1000);
  if (env.MODO_PRUEBA === "1") {
    pais = request.headers.get("x-drako-pais") || pais;
    ciudad = request.headers.get("x-drako-ciudad") || ciudad;
    ip = request.headers.get("x-drako-ip") || ip;
    const marca = request.headers.get("x-drako-ahora");
    if (marca && /^\d+$/.test(marca)) ahora = Number(marca);
  }
  return {
    ip: ip.replace(/[\u0000-\u001f]/g, "").trim().slice(0, 64),
    pais: pais.replace(/[\u0000-\u001f]/g, "").trim().slice(0, 8),
    ciudad: ciudad.replace(/[\u0000-\u001f]/g, "").trim().slice(0, 80),
    ahora,
  };
}
