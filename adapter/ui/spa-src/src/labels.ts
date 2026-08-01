// Labels legibles hand-written (NO codegen). Fuente única para panel, chips y tabla.
import type { EntityPayload, PerceptionEvent } from "./types/timonel.gen";
import { parsePoseKeypoints } from "./utils/poseSkeleton";

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

/** Clases / attrs del modelo (EN) → español. Se muestra como `en (es)`. */
const CLASS_ES: Record<string, string> = {
  // COCO frecuentes
  person: "persona",
  bicycle: "bicicleta",
  car: "auto",
  motorcycle: "moto",
  airplane: "avión",
  bus: "colectivo",
  train: "tren",
  truck: "camión",
  boat: "barco",
  "traffic light": "semáforo",
  "fire hydrant": "hidrante",
  "stop sign": "señal de pare",
  "parking meter": "parquímetro",
  bench: "banco",
  bird: "pájaro",
  cat: "gato",
  dog: "perro",
  horse: "caballo",
  sheep: "oveja",
  cow: "vaca",
  elephant: "elefante",
  bear: "oso",
  zebra: "cebra",
  giraffe: "jirafa",
  backpack: "mochila",
  umbrella: "paraguas",
  handbag: "cartera",
  tie: "corbata",
  suitcase: "valija",
  frisbee: "frisbee",
  skis: "esquíes",
  snowboard: "snowboard",
  "sports ball": "pelota",
  kite: "barrilete",
  "baseball bat": "bate",
  "baseball glove": "guante",
  skateboard: "skate",
  surfboard: "tabla de surf",
  "tennis racket": "raqueta",
  bottle: "botella",
  "wine glass": "copa",
  cup: "vaso",
  fork: "tenedor",
  knife: "cuchillo",
  spoon: "cuchara",
  bowl: "bowl",
  banana: "banana",
  apple: "manzana",
  sandwich: "sándwich",
  orange: "naranja",
  broccoli: "brócoli",
  carrot: "zanahoria",
  "hot dog": "hot dog",
  pizza: "pizza",
  donut: "dona",
  cake: "torta",
  chair: "silla",
  couch: "sofá",
  "potted plant": "maceta",
  bed: "cama",
  "dining table": "mesa",
  toilet: "inodoro",
  tv: "televisor",
  laptop: "notebook",
  mouse: "mouse",
  remote: "control remoto",
  keyboard: "teclado",
  "cell phone": "celular",
  microwave: "microondas",
  oven: "horno",
  toaster: "tostadora",
  sink: "pileta",
  refrigerator: "heladera",
  book: "libro",
  clock: "reloj",
  vase: "jarrón",
  scissors: "tijera",
  "teddy bear": "oso de peluche",
  hairdrier: "secador",
  toothbrush: "cepillo de dientes",
  // Vehículos / attrs PaddleX
  vehicle: "vehículo",
  sedan: "sedán",
  suv: "SUV",
  van: "van",
  pickup: "pickup",
  hitch: "enganche",
  unknown: "desconocido",
  desconocido: "desconocido",
  // Colores
  red: "rojo",
  blue: "azul",
  green: "verde",
  yellow: "amarillo",
  white: "blanco",
  black: "negro",
  brown: "marrón",
  grey: "gris",
  gray: "gris",
  purple: "violeta",
  pink: "rosa",
  cyan: "cian",
  silver: "plata",
  gold: "dorado",
  // Persona attrs
  male: "hombre",
  female: "mujer",
  adult: "adulto",
  child: "niño",
  elderly: "adulto mayor",
  front: "frente",
  back: "espalda",
  side: "perfil",
  left: "izquierda",
  right: "derecha",
  face: "cara",
  pose: "pose",
};

function typeLabel(entityType: string): string {
  return ENTITY_LABELS[entityType] ?? entityType;
}

/** `person` → `person (persona)`; sin traducción → original. */
export function displayClass(raw: string | null | undefined): string {
  if (!raw) return "";
  const trimmed = raw.trim();
  if (!trimmed) return "";
  const es = CLASS_ES[trimmed.toLowerCase()];
  if (!es) return trimmed;
  // Evitar "persona (persona)" si ya viene en español.
  if (trimmed.toLowerCase() === es.toLowerCase()) return trimmed;
  return `${trimmed} (${es})`;
}

/** String corto para chip/tabla; prioriza el campo más específico del payload. */
export function describeEvent(event: PerceptionEvent): string {
  const p = event.payload as EntityPayload;
  switch (p.entity_type) {
    case "vehicle": {
      const parts = [
        p.plate_text,
        displayClass(p.vehicle_type),
        displayClass(p.color),
      ].filter(Boolean);
      return parts.length ? parts.join(" · ") : "vehículo";
    }
    case "object": {
      const parts: string[] = [
        displayClass(p.class_name) || typeLabel("object"),
      ];
      const person = p.person;
      if (person && typeof person === "object") {
        const gender = person.gender;
        const age = person.age_group;
        const direction = person.direction;
        const upper = person.upper_color;
        if (typeof gender === "string" && gender) parts.push(displayClass(gender));
        if (typeof age === "string" && age) parts.push(displayClass(age));
        if (typeof direction === "string" && direction) parts.push(displayClass(direction));
        if (typeof upper === "string" && upper) parts.push(displayClass(upper));
      }
      return parts.join(" · ");
    }
    case "text": {
      const t = p.text?.trim();
      if (!t) return typeLabel("text");
      return t.length > 20 ? `${t.slice(0, 20)}…` : t;
    }
    case "pose": {
      const n = parsePoseKeypoints((p as { keypoints?: unknown }).keypoints).length;
      return n > 0 ? `Pose · ${n} pts` : typeLabel("pose");
    }
    case "face":
      return displayClass(
        (p as { class_name?: string }).class_name?.trim() || "face",
      );
    case "face_id":
      return p.identity ?? "identidad";
    case "sign":
    case "scene_cls":
    case "instance":
    case "small_object":
    case "anomaly":
    case "open_vocab":
      return displayClass(p.class_name?.trim()) || typeLabel(p.entity_type);
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
        chips: top.map(([name, pct]) => `${displayClass(name)} ${pct}%`),
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
