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
    case "vehicle":
      return p.vehicle_type ?? "vehículo";
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
