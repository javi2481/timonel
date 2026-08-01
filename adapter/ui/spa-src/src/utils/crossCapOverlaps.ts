// Solapes cross-capability: IoU entre bboxes de entity_types distintos.
// Candidatos = pistas; el front no adjudica (sin NMS). Solo métrica honesta.
import type { PerceptionEvent } from "../types/timonel.gen";
import { eventBbox } from "./eventId";

export interface OverlapPair {
  a: string;
  b: string;
  iou: number;
}

export interface CrossCapOverlaps {
  count: number;
  pairs: OverlapPair[];
}

/** IoU de dos bboxes [x1,y1,x2,y2] (orden de esquinas indiferente). */
export function bboxIoU(a: number[], b: number[]): number {
  const ax1 = Math.min(a[0], a[2]);
  const ay1 = Math.min(a[1], a[3]);
  const ax2 = Math.max(a[0], a[2]);
  const ay2 = Math.max(a[1], a[3]);
  const bx1 = Math.min(b[0], b[2]);
  const by1 = Math.min(b[1], b[3]);
  const bx2 = Math.max(b[0], b[2]);
  const by2 = Math.max(b[1], b[3]);

  const ix1 = Math.max(ax1, bx1);
  const iy1 = Math.max(ay1, by1);
  const ix2 = Math.min(ax2, bx2);
  const iy2 = Math.min(ay2, by2);
  const iw = Math.max(0, ix2 - ix1);
  const ih = Math.max(0, iy2 - iy1);
  const inter = iw * ih;
  if (inter <= 0) return 0;

  const areaA = (ax2 - ax1) * (ay2 - ay1);
  const areaB = (bx2 - bx1) * (by2 - by1);
  const union = areaA + areaB - inter;
  return union > 0 ? inter / union : 0;
}

/**
 * Pares con entity_type distinto e IoU ≥ threshold.
 * Un par de tipos se cuenta una vez (máximo IoU entre instancias de esos tipos).
 */
export function countCrossCapOverlaps(
  events: PerceptionEvent[],
  threshold = 0.3,
): CrossCapOverlaps {
  const withBox = events
    .map((e) => ({ type: e.entity_type, bbox: eventBbox(e) }))
    .filter((e): e is { type: string; bbox: number[] } => e.bbox !== null);

  const bestByPair = new Map<string, number>();

  for (let i = 0; i < withBox.length; i++) {
    for (let j = i + 1; j < withBox.length; j++) {
      const a = withBox[i];
      const b = withBox[j];
      if (a.type === b.type) continue;
      const iou = bboxIoU(a.bbox, b.bbox);
      if (iou < threshold) continue;
      const key = [a.type, b.type].sort().join("|");
      const prev = bestByPair.get(key) ?? 0;
      if (iou > prev) bestByPair.set(key, iou);
    }
  }

  const pairs: OverlapPair[] = [...bestByPair.entries()]
    .map(([key, iou]) => {
      const [a, b] = key.split("|");
      return { a, b, iou };
    })
    .sort((x, y) => y.iou - x.iou);

  return { count: pairs.length, pairs };
}
