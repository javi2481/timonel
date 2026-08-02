// CapabilityPanel — listado plano + semáforo verde/amarillo/rojo.
// Servicio: Verde = active && serving. Amarillo = prendiendo. Rojo = inactiva/error.
// Tras analizar: verdes las que tuvieron hits; rojas las activas sin hits.
// Las cajas no se muestran solas: click en una capa con hits → mostrar/ocultar.
import type { CapabilityEntry } from "../api/client";
import { ENTITY_LABELS } from "../labels";
import type { SessionStatus } from "../state/session";
import type { PerceptionEvent } from "../types/timonel.gen";
import { CapIcon } from "./CapIcon";

/** Orden de producto (alineado a adapter _SPA_CAPABILITY_DEFS). */
const CAP_ORDER: string[] = [
  "object",
  "face",
  "pose",
  "vehicle",
  "text",
  "scene",
  "face_id",
  "sign",
  "open_vocab",
  "scene_cls",
  "instance",
  "small_object",
  "anomaly",
];

export type TrafficLight = "green" | "yellow" | "red";

/** Semáforo de servicio (capa prendida / levantando / apagada). */
export function trafficLightFor(entry: CapabilityEntry | undefined): TrafficLight {
  if (!entry || !entry.available) return "red";
  if (entry.error) return "red";
  if (entry.active && entry.serving) return "green";
  if (entry.active && !entry.serving) return "yellow";
  return "red";
}

function analysisComplete(status: SessionStatus): boolean {
  return status === "ready" || status === "empty" || status === "degraded";
}

/** Tras análisis: verde si hubo hits, rojo si la capa corrió y no detectó nada. */
export function displayLightFor(
  entry: CapabilityEntry | undefined,
  hitCount: number,
  status: SessionStatus,
): TrafficLight {
  const service = trafficLightFor(entry);
  if (service !== "green" || !analysisComplete(status)) return service;
  return hitCount > 0 ? "green" : "red";
}

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  catalog: Record<string, CapabilityEntry>;
  status: SessionStatus;
  onToggleVisible: (entityType: string, visible: boolean) => void;
  onActivate?: (entityType: string) => void;
  onShowHits: () => void;
  onHideAll: () => void;
}

export function CapabilityPanel({
  events,
  visibility,
  catalog,
  status,
  onToggleVisible,
  onActivate,
  onShowHits,
  onHideAll,
}: Props) {
  const counts = new Map<string, number>();
  for (const e of events) {
    counts.set(e.entity_type, (counts.get(e.entity_type) ?? 0) + 1);
  }

  const items = CAP_ORDER.filter((t) => catalog[t]?.available === true);
  const analyzed = analysisComplete(status);
  const greenCount = items.filter(
    (t) => displayLightFor(catalog[t], counts.get(t) ?? 0, status) === "green",
  ).length;
  const yellowCount = items.filter((t) => trafficLightFor(catalog[t]) === "yellow").length;

  return (
    <div className="tm-capability-panel">
      <div className="tm-cap-legend">
        <span>
          {analyzed
            ? `${greenCount} con hits`
            : `${greenCount} activas`}
          {yellowCount > 0 ? ` · ${yellowCount} prendiendo` : ""}
        </span>
        <div className="tm-cap-actions-inline">
          <button type="button" className="tm-cap-action" onClick={onShowHits}>
            Mostrar hits
          </button>
          <button type="button" className="tm-cap-action" onClick={onHideAll}>
            Ocultar
          </button>
        </div>
      </div>
      <div className="tm-capability-list">
        {items.map((entityType) => {
          const entry = catalog[entityType];
          const serviceLight = trafficLightFor(entry);
          const count = counts.get(entityType) ?? 0;
          const light = displayLightFor(entry, count, status);
          const label = ENTITY_LABELS[entityType] ?? entityType;
          const visibleChecked = visibility[entityType] === true;
          const canToggleCanvas = serviceLight === "green" && count > 0;
          const canPrender =
            serviceLight === "red" && !!onActivate && entry?.available;
          const canvasOff = canToggleCanvas && !visibleChecked;

          const rowClass = [
            "tm-capability-row",
            `tm-cap-light-${light}`,
            canToggleCanvas ? "tm-cap-toggleable" : "",
            canvasOff ? "tm-cap-canvas-off" : "",
            canToggleCanvas && visibleChecked ? "tm-cap-hit" : "",
            canToggleCanvas && !visibleChecked ? "tm-cap-miss" : "",
          ]
            .filter(Boolean)
            .join(" ");

          const title =
            entry?.error ||
            (canToggleCanvas
              ? visibleChecked
                ? "Ocultar en el canvas"
                : "Mostrar en el canvas"
              : analyzed && serviceLight === "green" && count === 0
                ? "Sin detecciones en esta imagen"
                : undefined);

          return (
            <div
              key={entityType}
              className={rowClass}
              title={title}
              role={canToggleCanvas ? "button" : undefined}
              tabIndex={canToggleCanvas ? 0 : undefined}
              aria-pressed={canToggleCanvas ? visibleChecked : undefined}
              onClick={() => {
                if (canToggleCanvas) {
                  onToggleVisible(entityType, !visibleChecked);
                }
              }}
              onKeyDown={(ev) => {
                if (!canToggleCanvas) return;
                if (ev.key === "Enter" || ev.key === " ") {
                  ev.preventDefault();
                  onToggleVisible(entityType, !visibleChecked);
                }
              }}
            >
              <span
                className={`tm-cap-dot tm-cap-dot-${light}`}
                aria-label={
                  light === "green"
                    ? analyzed
                      ? "con detecciones"
                      : "activa"
                    : light === "yellow"
                      ? "prendiendo"
                      : analyzed && serviceLight === "green"
                        ? "sin detecciones"
                        : "inactiva"
                }
              />
              <span className="tm-capability-icon">
                <CapIcon entityType={entityType} />
              </span>
              <div className="tm-capability-body">
                <span className="tm-capability-label">
                  {label}
                  {count > 0 ? ` · ${count}` : ""}
                </span>
                {serviceLight === "yellow" && (
                  <span className="tm-cap-warming">Levantando…</span>
                )}
                {serviceLight === "red" && entry?.error && (
                  <span className="tm-cap-err">{entry.error}</span>
                )}
              </div>
              <div className="tm-cap-row-actions">
                {canToggleCanvas && (
                  <span
                    className={
                      visibleChecked
                        ? "tm-cap-check tm-cap-check-on"
                        : "tm-cap-check"
                    }
                    aria-hidden="true"
                    title={visibleChecked ? "Visible en el canvas" : "Oculta"}
                  >
                    {visibleChecked ? (
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M3.5 8.5 6.5 11.5 12.5 4.5"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : null}
                  </span>
                )}
                {canPrender && (
                  <button
                    type="button"
                    className="tm-cap-activate"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onActivate(entityType);
                    }}
                  >
                    Prender
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
