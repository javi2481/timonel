/** Punto 2D en píxeles de la imagen (mismo espacio que bbox / SVG viewBox). */
export type PolyPoint = { x: number; y: number };

/** Extrae polígono OCR `[[x,y], …]` del payload text. */
export function parseEventPolygon(raw: unknown): PolyPoint[] {
  if (!Array.isArray(raw) || raw.length < 3) return [];
  const pts: PolyPoint[] = [];
  for (const item of raw) {
    if (!Array.isArray(item) || item.length < 2) return [];
    const x = typeof item[0] === "number" ? item[0] : Number(item[0]);
    const y = typeof item[1] === "number" ? item[1] : Number(item[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
    pts.push({ x, y });
  }
  return pts.length >= 3 ? pts : [];
}

export function polygonToSvgPoints(pts: PolyPoint[]): string {
  return pts.map((p) => `${p.x},${p.y}`).join(" ");
}

/** Colores CSS-válidos típicos del attr vehicle (PaddleX EN). */
const CSS_COLOR_NAMES = new Set([
  "red",
  "blue",
  "green",
  "yellow",
  "white",
  "black",
  "brown",
  "grey",
  "gray",
  "orange",
  "purple",
  "pink",
  "cyan",
  "silver",
  "gold",
]);

/** Si el nombre de color del modelo es usable como CSS, lo devuelve; si no, null. */
export function cssColorFromLabel(name: string | null | undefined): string | null {
  if (!name) return null;
  const key = name.trim().toLowerCase();
  if (!CSS_COLOR_NAMES.has(key)) return null;
  // Blanco/amarillo/plateado: borde visible sobre chips claros.
  if (key === "white" || key === "yellow" || key === "silver" || key === "gold") {
    return key;
  }
  return key;
}
