// Cliente HTTP tipado para la SPA.
//
// Mismo origen que la API (`adapter/app.py` sirve /app/ y los endpoints REST
// desde el mismo proceso FastAPI) — rutas relativas a la raíz, no a `/app/`.
// Sin caché de navegador en /media/original (ver X-Generation + no-store).
import type { PerceptionEvent } from "../types/timonel.gen";

export interface MediaItem {
  name: string;
  type: string;
}

export interface CurrentMediaResponse {
  name: string | null;
  type: string | null;
  generation: number;
  open_vocab_prompt?: string | null;
}

export interface UploadResponse {
  status: 0 | 1;
  msg: string;
  ok: boolean;
  name?: string;
  generation?: number;
  error?: string;
}

export interface ClearResponse {
  ok: boolean;
  name: string | null;
  generation: number;
}

export interface EventsEnvelope {
  count: number;
  total_emitted: number;
  tracks_active: number;
  degraded: boolean;
  /** Generación activa de la foto seleccionada (bump en upload/select/clear). */
  generation: number;
  /**
   * Última generación confirmada por un /ingest del bridge. `null` = todavía
   * ninguna. Completitud (Claude correction, NO `analysis_complete`):
   * `generation === last_ingest_generation`.
   */
  last_ingest_generation: number | null;
  events: PerceptionEvent[];
}

export interface HealthResponse {
  status: string;
  tracks_active: number;
  events_buffered: number;
  paddlex_degraded: boolean;
  TIMONEL_ENV: string;
  utc: string;
}

async function asJson<T>(res: Response): Promise<T> {
  const body = (await res.json()) as T;
  return body;
}

export async function uploadMedia(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/media/upload", { method: "POST", body: form });
  return asJson<UploadResponse>(res);
}

export async function getCurrentMedia(): Promise<CurrentMediaResponse> {
  const res = await fetch("/media/current");
  return asJson<CurrentMediaResponse>(res);
}

export async function clearMedia(): Promise<ClearResponse> {
  const res = await fetch("/media/clear", { method: "POST" });
  return asJson<ClearResponse>(res);
}

export async function listMedia(): Promise<MediaItem[]> {
  const res = await fetch("/media/list");
  const body = await asJson<{ items: MediaItem[] }>(res);
  return Array.isArray(body.items) ? body.items : [];
}

export interface SelectMediaResponse {
  ok: boolean;
  name?: string;
  generation?: number;
  error?: string;
}

export async function selectMedia(name: string): Promise<SelectMediaResponse> {
  const res = await fetch("/media/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const body = await asJson<SelectMediaResponse>(res);
  if (!res.ok) {
    return { ok: false, error: body.error || `select failed (${res.status})` };
  }
  return body;
}

/** URL directa para <img src>; `generation` en query evita reusar caché intermedia. */
export function originalMediaUrl(generation?: number): string {
  return generation === undefined
    ? "/media/original"
    : `/media/original?generation=${generation}`;
}

export async function getEvents(limit = 100): Promise<EventsEnvelope> {
  const res = await fetch(`/events?limit=${limit}`);
  return asJson<EventsEnvelope>(res);
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/health");
  return asJson<HealthResponse>(res);
}

/** Entry keyed by SPA entity_type from GET/PUT /capabilities. */
export interface CapabilityEntry {
  name: string;
  available: boolean;
  active: boolean;
  serving?: boolean;
  runtime?: string;
  error?: string;
  critical?: boolean;
}

export interface CapabilitiesResponse {
  generation: number;
  capabilities: Record<string, CapabilityEntry>;
}

export async function getCapabilities(): Promise<CapabilitiesResponse> {
  const res = await fetch("/capabilities");
  return asJson<CapabilitiesResponse>(res);
}

/** Partial merge of runtime active flags. */
export async function putCapabilities(
  active: Record<string, boolean>,
): Promise<CapabilitiesResponse> {
  const res = await fetch("/capabilities", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(err.error || `PUT /capabilities failed (${res.status})`);
  }
  return asJson<CapabilitiesResponse>(res);
}
