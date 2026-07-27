// CapabilityPanel — toggles de visibilidad (client-only).
// Inferencia: bridge corre todo lo available; verde=hit, rojo=miss.
import type { CapabilityEntry } from "../api/client";
import { ENTITY_LABELS } from "../labels";
import type { SessionStatus } from "../state/session";
import type { PerceptionEvent } from "../types/epp.gen";

interface CapabilityDef {
  entityType: string;
}

const GROUPS: { title: string; items: CapabilityDef[] }[] = [
  {
    title: "Base",
    items: [
      { entityType: "vehicle" },
      { entityType: "object" },
      { entityType: "face" },
    ],
  },
  {
    title: "Extendida",
    items: [
      { entityType: "scene" },
      { entityType: "pose" },
      { entityType: "text" },
      { entityType: "face_id" },
    ],
  },
  {
    title: "Experimental",
    items: [
      { entityType: "sign" },
      { entityType: "scene_cls" },
      { entityType: "instance" },
      { entityType: "small_object" },
      { entityType: "anomaly" },
      { entityType: "open_vocab" },
    ],
  },
];

type CapState = "pending" | "hit" | "miss" | "unavailable";

function EyeIcon({ off }: { off?: boolean }) {
  if (off) {
    return (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    );
  }
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}

function analysisComplete(status: SessionStatus): boolean {
  return status === "ready" || status === "degraded" || status === "empty";
}

function isAnalyzing(status: SessionStatus): boolean {
  return status === "uploading" || status === "processing";
}

function capState(
  status: SessionStatus,
  available: boolean,
  count: number,
): CapState {
  if (!available) return "unavailable";
  if (isAnalyzing(status)) return "pending";
  if (!analysisComplete(status)) return "unavailable";
  return count > 0 ? "hit" : "miss";
}

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  catalog: Record<string, CapabilityEntry>;
  status: SessionStatus;
  onToggleVisible: (entityType: string, visible: boolean) => void;
  onShowHits: () => void;
  onHideAll: () => void;
}

export function CapabilityPanel({
  events,
  visibility,
  catalog,
  status,
  onToggleVisible,
  onShowHits,
  onHideAll,
}: Props) {
  const counts = new Map<string, number>();
  for (const e of events) {
    counts.set(e.entity_type, (counts.get(e.entity_type) ?? 0) + 1);
  }

  const hitTypes = GROUPS.flatMap((g) => g.items)
    .map((i) => i.entityType)
    .filter((t) => (counts.get(t) ?? 0) > 0);
  const complete = analysisComplete(status);
  const hasHits = hitTypes.length > 0;

  return (
    <div className="vi-capability-panel">
      <div className="vi-cap-legend">
        <span title="Solo ocultar/mostrar cajas y etiquetas (sin reanalizar)">
          <EyeIcon /> mostrar / ocultar
        </span>
      </div>
      <div className="vi-cap-actions">
        <button
          type="button"
          className="vi-cap-action"
          disabled={!complete || !hasHits}
          onClick={onShowHits}
        >
          Mostrar hits
        </button>
        <button
          type="button"
          className="vi-cap-action"
          disabled={!complete || !hasHits}
          onClick={onHideAll}
        >
          Ocultar todo
        </button>
      </div>
      {GROUPS.map((group) => (
        <div className="vi-capability-group" key={group.title}>
          <div className="vi-capability-group-title">{group.title}</div>
          {group.items.map((item) => {
            const label = ENTITY_LABELS[item.entityType] ?? item.entityType;
            const count = counts.get(item.entityType) ?? 0;
            const entry = catalog[item.entityType];
            const available = entry?.available === true;
            const state = capState(status, available, count);
            const visibleChecked = visibility[item.entityType] === true;
            const canToggle = state === "hit";
            const labelText =
              state === "hit" ? `${label} · ${count}` : label;

            return (
              <div
                key={item.entityType}
                className={`vi-capability-item vi-cap-${state}`}
              >
                <span className="vi-capability-label">{labelText}</span>
                <span
                  className={`vi-cap-status vi-cap-status-${state}`}
                  title={
                    state === "pending"
                      ? "Analizando…"
                      : state === "hit"
                        ? `${count} detección${count === 1 ? "" : "es"}`
                        : state === "miss"
                          ? "Sin detecciones"
                          : "No disponible en este deploy"
                  }
                  aria-hidden
                />
                <button
                  type="button"
                  className={`vi-eye${!visibleChecked || !canToggle ? " off" : ""}`}
                  disabled={!canToggle}
                  title={
                    canToggle
                      ? visibleChecked
                        ? "Ocultar cajas"
                        : "Mostrar cajas"
                      : state === "pending"
                        ? "Analizando…"
                        : state === "miss"
                          ? "Sin detecciones"
                          : "No disponible"
                  }
                  aria-label={`${label} visible`}
                  aria-pressed={canToggle && visibleChecked}
                  onClick={() => onToggleVisible(item.entityType, !visibleChecked)}
                >
                  <EyeIcon off={!canToggle || !visibleChecked} />
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
