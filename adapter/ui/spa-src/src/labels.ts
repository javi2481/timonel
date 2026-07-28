// Labels legibles hand-written (NO codegen). Fuente única para panel, chips y tabla.
import type { EntityPayload, PerceptionEvent } from "./types/epp.gen";

export const ENTITY_LABELS: Record<string, string> = {
  vehicle: "Vehículo",
  object: "Objeto",
  face: "Cara",
  scene: "Escena",
  pose: "Pose",
  text: "Texto",
  face_id: "Identidad",
  sign: "Señal",
  scene_cls: "Clasif. escena",
  instance: "Instancia",
  small_object: "Objeto pequeño",
  anomaly: "Anomalía",
  open_vocab: "Vocab. abierto",
};

function typeLabel(entityType: string): string {
  return ENTITY_LABELS[entityType] ?? entityType;
}

/** String corto para chip/tabla; prioriza el campo más específico del payload. */
export function describeEvent(event: PerceptionEvent): string {
  const p = event.payload as EntityPayload;
  switch (p.entity_type) {
    case "vehicle": {
      const parts = [p.vehicle_type, p.color].filter(Boolean);
      return parts.length ? parts.join(" · ") : "vehículo";
    }
    case "object":
      return p.class_name ?? typeLabel("object");
    case "text": {
      const t = p.text?.trim();
      if (!t) return typeLabel("text");
      return t.length > 20 ? `${t.slice(0, 20)}…` : t;
    }
    case "face_id":
      return p.identity ?? "identidad";
    case "sign":
    case "scene_cls":
    case "instance":
    case "small_object":
    case "anomaly":
    case "open_vocab":
      return p.class_name?.trim() || typeLabel(p.entity_type);
    default:
      return typeLabel(event.entity_type);
  }
}

const MAX_SUMMARY_CHIPS = 3;

/** Top labels para el panel de capacidades (máx. 3 + restante). */
export function summarizeCapabilityChips(
  entityType: string,
  events: PerceptionEvent[],
): { chips: string[]; extra: number } {
  const mine = events.filter((e) => e.entity_type === entityType);
  if (mine.length === 0) return { chips: [], extra: 0 };

  if (entityType === "scene") {
    const ratios = sceneRatiosFromEvent(mine[0]);
    if (ratios.length > 0) {
      const top = ratios.slice(0, MAX_SUMMARY_CHIPS);
      return {
        chips: top.map(([name, pct]) => `${name} ${pct}%`),
        extra: Math.max(0, ratios.length - MAX_SUMMARY_CHIPS),
      };
    }
  }

  const counts = new Map<string, number>();
  for (const e of mine) {
    const label = describeEvent(e).trim() || typeLabel(entityType);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  const ranked = [...counts.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
  const chips = ranked
    .slice(0, MAX_SUMMARY_CHIPS)
    .map(([label, n]) => (n > 1 ? `${label} ×${n}` : label));
  return { chips, extra: Math.max(0, ranked.length - MAX_SUMMARY_CHIPS) };
}

function sceneRatiosFromEvent(event: PerceptionEvent): [string, number][] {
  const p = event.payload as EntityPayload;
  if (p.entity_type !== "scene" || !p.scene || typeof p.scene !== "object") {
    return [];
  }
  const raw = (p.scene as { ratios?: unknown }).ratios;
  if (!raw || typeof raw !== "object") return [];
  const entries: [string, number][] = [];
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    const n = typeof v === "number" ? v : Number(v);
    if (!Number.isFinite(n) || n <= 0) continue;
    entries.push([k, Math.round(n * 100)]);
  }
  entries.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return entries;
}
