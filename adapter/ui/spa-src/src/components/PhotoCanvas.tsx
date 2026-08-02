// PhotoCanvas — foto original + overlay SVG + chips HTML + estados de sesión.
//
// viewBox = naturalWidth×naturalHeight; chips/popover en % de naturalSize
// (nunca constantes de escena del mock).
import { useEffect, useRef, useState } from "react";
import { originalMediaUrl } from "../api/client";
import { colorForEvent } from "../colors/entityColors.gen";
import { describeEvent } from "../labels";
import type { SessionStatus } from "../state/session";
import type { PerceptionEvent } from "../types/timonel.gen";
import { bboxToPercent, eventBbox, eventId } from "../utils/eventId";
import {
  cssColorFromLabel,
  parseEventPolygon,
  polygonToSvgPoints,
} from "../utils/overlayGeom";
import {
  eventPoseKeypoints,
  visiblePoseBones,
  visiblePoseJoints,
} from "../utils/poseSkeleton";

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
  onImageLoaded: (loaded: boolean) => void;
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
  onImageLoaded,
}: Props) {
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    setNaturalSize(null);
    onImageLoaded(false);
  }, [generation, onImageLoaded]);

  const visibleEntries = events
    .map((event, index) => ({ event, index, id: eventId(event, index), bbox: eventBbox(event) }))
    .filter((entry) => entry.bbox !== null && visibility[entry.event.entity_type] === true);

  const selected = visibleEntries.find((entry) => entry.id === selectedId) ?? null;

  return (
    <div className="tm-stage">
      <div className="tm-canvas-card">
        <div className="tm-canvas">
          <img
            key={generation}
            className="tm-canvas-img"
            src={originalMediaUrl(generation)}
            alt="Foto activa"
            onLoad={(e) => {
              const img = e.currentTarget;
              setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
              onImageLoaded(true);
            }}
            onError={() => {
              setNaturalSize(null);
              onImageLoaded(false);
            }}
          />
          {naturalSize && (
            <svg
              className="tm-canvas-overlay"
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
                const strokeW = isHovered || isSelected ? 4 : 2;
                const payload = event.payload as {
                  keypoints?: unknown;
                  polygon?: unknown;
                  plate_text?: string | null;
                  color?: string | null;
                };
                const poseJoints =
                  event.entity_type === "pose" ? eventPoseKeypoints(payload) : [];
                const bones = visiblePoseBones(poseJoints);
                const joints = visiblePoseJoints(poseJoints);
                const textPoly =
                  event.entity_type === "text" ? parseEventPolygon(payload.polygon) : [];
                const plate =
                  event.entity_type === "vehicle" && payload.plate_text
                    ? String(payload.plate_text).trim()
                    : "";
                // Esqueleto fino: escala baja respecto al bbox.
                const boxH = Math.max(1, Math.abs(y2 - y1));
                const boxW = Math.max(1, Math.abs(x2 - x1));
                const boneW = Math.max(1, Math.min(2.5, boxH * 0.005));
                const jointR = Math.max(1.8, Math.min(3.5, boxH * 0.008));
                const left = Math.min(x1, x2);
                const top = Math.min(y1, y2);
                const bottom = Math.max(y1, y2);
                return (
                  <g key={id} pointerEvents="none">
                    <rect
                      x={left}
                      y={top}
                      width={boxW}
                      height={boxH}
                      fill={isSelected && textPoly.length === 0 ? color : "transparent"}
                      fillOpacity={isSelected && textPoly.length === 0 ? 0.15 : 0}
                      stroke={color}
                      strokeWidth={textPoly.length >= 3 ? Math.max(1, strokeW - 1) : strokeW}
                      strokeDasharray={textPoly.length >= 3 ? "6 4" : undefined}
                      opacity={textPoly.length >= 3 ? 0.55 : 1}
                    />
                    {textPoly.length >= 3 && (
                      <polygon
                        points={polygonToSvgPoints(textPoly)}
                        fill={color}
                        fillOpacity={isSelected ? 0.22 : 0.08}
                        stroke={color}
                        strokeWidth={strokeW}
                        strokeLinejoin="round"
                      />
                    )}
                    {bones.map((b, i) => (
                      <line
                        key={`${id}-bone-${i}`}
                        x1={b.x1}
                        y1={b.y1}
                        x2={b.x2}
                        y2={b.y2}
                        stroke={b.color}
                        strokeWidth={boneW}
                        strokeLinecap="round"
                        opacity={0.92}
                      />
                    ))}
                    {joints.map((j) => (
                      <circle
                        key={`${id}-joint-${j.index}`}
                        cx={j.x}
                        cy={j.y}
                        r={jointR}
                        fill={j.color}
                        stroke="#0a0e13"
                        strokeWidth={Math.max(0.8, boneW * 0.5)}
                        opacity={0.95}
                      />
                    ))}
                    {plate && (
                      <VehiclePlateBadge
                        id={id}
                        plate={plate}
                        left={left}
                        bottom={bottom}
                        boxW={boxW}
                        boxH={boxH}
                        color={color}
                        hot={isHovered || isSelected}
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          )}
          {naturalSize && (
            <div className="tm-chip-layer">
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
                const vehicleColor =
                  event.entity_type === "vehicle"
                    ? cssColorFromLabel((event.payload as { color?: string | null }).color)
                    : null;
                const personUpper =
                  event.entity_type === "object"
                    ? cssColorFromLabel(
                        String(
                          ((event.payload as { person?: { upper_color?: unknown } | null })
                            .person?.upper_color as string | undefined) ?? "",
                        ) || null,
                      )
                    : null;
                const swatch = vehicleColor ?? personUpper;
                return (
                  <span
                    key={id}
                    className={`tm-chip${flipBelow ? " below" : ""}${isHot ? " hot" : ""}`}
                    style={{
                      left: `${leftPct}%`,
                      top: `${topPct}%`,
                      background: color,
                      color: contrastInk(color),
                      zIndex: isHot ? 5 : 1,
                    }}
                  >
                    {swatch && (
                      <span
                        className="tm-chip-swatch"
                        style={{ background: swatch }}
                        aria-hidden
                      />
                    )}
                    {describeEvent(event)}
                    <span className="tm-chip-conf">· {conf}%</span>
                  </span>
                );
              })}
            </div>
          )}
          {status === "degraded" && (
            <div className="tm-banner">PaddleX no disponible — mostrando lo detectado</div>
          )}
          {status === "empty" && (
            <div className="tm-overlay">
              <div className="tm-empty-card">
                <div className="tm-empty-big">Análisis completo — sin detecciones</div>
                <div>Ningún pipeline encontró nada. Probá con otra foto.</div>
              </div>
            </div>
          )}
          {status === "error" && (
            <div className="tm-overlay">
              <div className="tm-empty-card">
                <div className="tm-empty-big">Error</div>
                <div>{errorMessage ?? "Falló el análisis."}</div>
                <button type="button" className="tm-btn tm-btn-primary" onClick={onRetry}>
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
        </div>
      </div>
    </div>
  );
}

function VehiclePlateBadge({
  id,
  plate,
  left,
  bottom,
  boxW,
  boxH,
  color,
  hot,
}: {
  id: string;
  plate: string;
  left: number;
  bottom: number;
  boxW: number;
  boxH: number;
  color: string;
  hot: boolean;
}) {
  const fontSize = Math.max(10, Math.min(18, boxW * 0.12, boxH * 0.08));
  const padX = fontSize * 0.45;
  const padY = fontSize * 0.28;
  const textW = plate.length * fontSize * 0.62;
  const badgeW = textW + padX * 2;
  const badgeH = fontSize + padY * 2;
  const bx = left + (boxW - badgeW) / 2;
  const by = bottom - badgeH - Math.max(4, boxH * 0.03);
  return (
    <g>
      <rect
        x={bx}
        y={by}
        width={badgeW}
        height={badgeH}
        rx={Math.max(2, fontSize * 0.15)}
        fill="#0a0e13"
        stroke={color}
        strokeWidth={hot ? 2.5 : 1.5}
        opacity={0.92}
      />
      <text
        x={bx + badgeW / 2}
        y={by + badgeH / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#f5f7fa"
        fontSize={fontSize}
        fontFamily="ui-monospace, SF Mono, Menlo, monospace"
        fontWeight={700}
        letterSpacing="0.04em"
      >
        {plate}
      </text>
                    <title id={`${id}-plate`}>{`patente ${plate}`}</title>
    </g>
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
        if (t?.closest?.(".tm-canvas-overlay")) return;
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
      className={`tm-popover${openLeft ? " open-left" : ""}${openUp ? " open-up" : ""}`}
      style={{ left: `${leftPct}%`, top: `${topPct}%` }}
      role="dialog"
      aria-label="Detalle del evento"
    >
      <button className="tm-popover-close" onClick={onClose} aria-label="Cerrar">
        ×
      </button>
      <div className="tm-popover-title">{describeEvent(event)}</div>
      <div className="tm-popover-row">confidence: {event.confidence.toFixed(2)}</div>
      {Object.entries(payload)
        .filter(([k, v]) => k !== "bbox" && v !== null && v !== undefined)
        .map(([k, v]) => {
          if (k === "keypoints") {
            const n = eventPoseKeypoints({ keypoints: v }).length;
            return (
              <div className="tm-popover-row" key={k}>
                keypoints: {n} joints
              </div>
            );
          }
          if (k === "polygon") {
            const n = parseEventPolygon(v).length;
            return (
              <div className="tm-popover-row" key={k}>
                polygon: {n} pts
              </div>
            );
          }
          if (k === "person" && v && typeof v === "object") {
            const attrs = Object.entries(v as Record<string, unknown>)
              .filter(([, av]) => av !== null && av !== undefined)
              .map(([ak, av]) => `${ak}=${String(av)}`)
              .join(", ");
            return (
              <div className="tm-popover-row" key={k}>
                person: {attrs || "—"}
              </div>
            );
          }
          return (
            <div className="tm-popover-row" key={k}>
              {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </div>
          );
        })}
    </div>
  );
}
