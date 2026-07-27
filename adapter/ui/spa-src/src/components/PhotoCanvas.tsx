// PhotoCanvas — foto original + overlay SVG + chips HTML + estados de sesión.
//
// viewBox = naturalWidth×naturalHeight; chips/popover en % de naturalSize
// (nunca constantes de escena del mock).
import { useEffect, useRef, useState } from "react";
import { originalMediaUrl } from "../api/client";
import { colorForEvent } from "../colors/entityColors.gen";
import { describeEvent } from "../labels";
import type { SessionStatus } from "../state/session";
import type { PerceptionEvent } from "../types/epp.gen";
import { bboxToPercent, eventBbox, eventId } from "../utils/eventId";

interface Props {
  generation: number;
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  hoveredId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  status: SessionStatus;
  errorMessage: string | null;
  onRetry: () => void;
  availableCapCount: number;
}

function contrastInk(hex: string): string {
  const h = hex.replace("#", "");
  if (h.length < 6) return "#e7eef6";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.55 ? "#0a0e13" : "#e7eef6";
}

/** Punto del cliente → coords del viewBox SVG (respeeta preserveAspectRatio). */
function clientToSvgPoint(
  svg: SVGSVGElement,
  clientX: number,
  clientY: number,
): { x: number; y: number } | null {
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;
  const pt = svg.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  const local = pt.matrixTransform(ctm.inverse());
  return { x: local.x, y: local.y };
}

function pointInBbox(x: number, y: number, bbox: number[]): boolean {
  const x1 = Math.min(bbox[0], bbox[2]);
  const x2 = Math.max(bbox[0], bbox[2]);
  const y1 = Math.min(bbox[1], bbox[3]);
  const y2 = Math.max(bbox[1], bbox[3]);
  return x >= x1 && x <= x2 && y >= y1 && y <= y2;
}

function bboxArea(bbox: number[]): number {
  return Math.abs(bbox[2] - bbox[0]) * Math.abs(bbox[3] - bbox[1]);
}

/** Hits bajo el cursor, más chica primero (para preferir cara sobre cuerpo, etc.). */
function hitsAtPoint<T extends { id: string; bbox: number[] | null }>(
  entries: T[],
  x: number,
  y: number,
): T[] {
  return entries
    .filter((e) => e.bbox !== null && pointInBbox(x, y, e.bbox as number[]))
    .slice()
    .sort((a, b) => bboxArea(a.bbox as number[]) - bboxArea(b.bbox as number[]));
}

/** Ciclo: más chica → siguientes → deseleccionar → otra vez. */
function nextOverlapSelection(hitIds: string[], selectedId: string | null): string | null {
  if (hitIds.length === 0) return null;
  if (selectedId === null) return hitIds[0];
  const idx = hitIds.indexOf(selectedId);
  if (idx < 0) return hitIds[0];
  if (idx === hitIds.length - 1) return null;
  return hitIds[idx + 1];
}

export function PhotoCanvas({
  generation,
  events,
  visibility,
  hoveredId,
  selectedId,
  onHover,
  onSelect,
  status,
  errorMessage,
  onRetry,
  availableCapCount,
}: Props) {
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const [showLabels, setShowLabels] = useState(true);

  const visibleEntries = events
    .map((event, index) => ({ event, index, id: eventId(event, index), bbox: eventBbox(event) }))
    .filter((entry) => entry.bbox !== null && visibility[entry.event.entity_type] === true);

  const selected = visibleEntries.find((entry) => entry.id === selectedId) ?? null;

  return (
    <div className="vi-stage">
      <div className="vi-canvas-card">
        <div className="vi-canvas-toolbar">
          <span>Detecciones</span>
          <label className="vi-lbl-toggle">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            etiquetas
          </label>
        </div>
        <div className="vi-canvas">
          <img
            key={generation}
            className="vi-canvas-img"
            src={originalMediaUrl(generation)}
            alt="Foto activa"
            onLoad={(e) => {
              const img = e.currentTarget;
              setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
            }}
          />
          {naturalSize && (
            <svg
              className="vi-canvas-overlay"
              viewBox={`0 0 ${naturalSize.w} ${naturalSize.h}`}
              preserveAspectRatio="xMidYMid meet"
              style={{ cursor: "crosshair" }}
              onMouseMove={(e) => {
                const svg = e.currentTarget;
                const pt = clientToSvgPoint(svg, e.clientX, e.clientY);
                if (!pt) return;
                const hits = hitsAtPoint(visibleEntries, pt.x, pt.y);
                const nextHover = hits[0]?.id ?? null;
                if (nextHover !== hoveredId) onHover(nextHover);
              }}
              onMouseLeave={() => onHover(null)}
              onClick={(e) => {
                const svg = e.currentTarget;
                const pt = clientToSvgPoint(svg, e.clientX, e.clientY);
                if (!pt) return;
                const hits = hitsAtPoint(visibleEntries, pt.x, pt.y);
                onSelect(nextOverlapSelection(hits.map((h) => h.id), selectedId));
              }}
            >
              {visibleEntries.map(({ event, id, bbox }) => {
                const [x1, y1, x2, y2] = bbox as number[];
                const color = colorForEvent(
                  event.entity_type,
                  (event.payload as { vehicle_type?: string | null }).vehicle_type,
                  event.candidate_ids[0],
                );
                const isHovered = id === hoveredId;
                const isSelected = id === selectedId;
                return (
                  <rect
                    key={id}
                    x={Math.min(x1, x2)}
                    y={Math.min(y1, y2)}
                    width={Math.abs(x2 - x1)}
                    height={Math.abs(y2 - y1)}
                    fill={isSelected ? color : "transparent"}
                    fillOpacity={isSelected ? 0.15 : 0}
                    stroke={color}
                    strokeWidth={isHovered || isSelected ? 4 : 2}
                    pointerEvents="none"
                  />
                );
              })}
            </svg>
          )}
          {naturalSize && showLabels && (
            <div className="vi-chip-layer">
              {visibleEntries.map(({ event, id, bbox }) => {
                const box = bbox as number[];
                const { leftPct, topPct } = bboxToPercent(box, naturalSize, "top-left");
                const flipBelow = Math.min(box[1], box[3]) / naturalSize.h < 0.04;
                const color = colorForEvent(
                  event.entity_type,
                  (event.payload as { vehicle_type?: string | null }).vehicle_type,
                  event.candidate_ids[0],
                );
                const isHot = id === hoveredId || id === selectedId;
                const conf = Math.round(event.confidence * 100);
                return (
                  <span
                    key={id}
                    className={`vi-chip${flipBelow ? " below" : ""}${isHot ? " hot" : ""}`}
                    style={{
                      left: `${leftPct}%`,
                      top: `${topPct}%`,
                      background: color,
                      color: contrastInk(color),
                      zIndex: isHot ? 5 : 1,
                    }}
                  >
                    {describeEvent(event)}
                    <span className="vi-chip-conf">· {conf}%</span>
                  </span>
                );
              })}
            </div>
          )}
          {status === "degraded" && (
            <div className="vi-banner">PaddleX no disponible — mostrando lo detectado</div>
          )}
          {status === "processing" && (
            <div className="vi-overlay vi-overlay-proc">
              <div>
                <div className="vi-spinner" />
                <div className="vi-overlay-msg">Analizando imagen…</div>
                <div className="vi-progress-indeterminate" aria-hidden>
                  <div className="vi-progress-indeterminate-bar" />
                </div>
                <div className="vi-overlay-sub">
                  {availableCapCount} capacidad{availableCapCount === 1 ? "" : "es"} disponible
                  {availableCapCount === 1 ? "" : "s"}
                </div>
              </div>
            </div>
          )}
          {status === "empty" && (
            <div className="vi-overlay">
              <div className="vi-empty-card">
                <div className="vi-empty-big">Análisis completo — sin detecciones</div>
                <div>Ningún pipeline encontró nada. Probá con otra foto.</div>
              </div>
            </div>
          )}
          {status === "error" && (
            <div className="vi-overlay">
              <div className="vi-empty-card">
                <div className="vi-empty-big">Error</div>
                <div>{errorMessage ?? "Falló el análisis."}</div>
                <button type="button" className="vi-btn vi-btn-primary" onClick={onRetry}>
                  Reintentar
                </button>
              </div>
            </div>
          )}
          {selected && naturalSize && (
            <EventPopover
              event={selected.event}
              bbox={selected.bbox as number[]}
              naturalSize={naturalSize}
              onClose={() => onSelect(null)}
            />
          )}
          {!naturalSize && status !== "error" && (
            <div className="vi-canvas-loading">Cargando foto…</div>
          )}
        </div>
      </div>
    </div>
  );
}

function EventPopover({
  event,
  bbox,
  naturalSize,
  onClose,
}: {
  event: PerceptionEvent;
  bbox: number[];
  naturalSize: { w: number; h: number };
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { leftPct, topPct } = bboxToPercent(bbox, naturalSize, "bottom-left");
  // Flip horizontal/vertical near edges (clamp inside canvas).
  const openLeft = leftPct > 70;
  const openUp = topPct > 70;
  const payload = event.payload as unknown as Record<string, unknown>;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        // El overlay maneja el clic (ciclo de cajas superpuestas); no resetear acá.
        const t = e.target as Element | null;
        if (t?.closest?.(".vi-canvas-overlay")) return;
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDoc);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDoc);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className={`vi-popover${openLeft ? " open-left" : ""}${openUp ? " open-up" : ""}`}
      style={{ left: `${leftPct}%`, top: `${topPct}%` }}
      role="dialog"
      aria-label="Detalle del evento"
    >
      <button className="vi-popover-close" onClick={onClose} aria-label="Cerrar">
        ×
      </button>
      <div className="vi-popover-title">{describeEvent(event)}</div>
      <div className="vi-popover-row">confidence: {event.confidence.toFixed(2)}</div>
      {Object.entries(payload)
        .filter(([k, v]) => k !== "bbox" && v !== null && v !== undefined)
        .map(([k, v]) => (
          <div className="vi-popover-row" key={k}>
            {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </div>
        ))}
    </div>
  );
}
