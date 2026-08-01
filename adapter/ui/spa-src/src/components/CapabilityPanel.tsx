// CapabilityPanel — toggles de visibilidad (client-only).
// Inferencia: bridge corre todo lo available; verde=hit, rojo=miss.
// Chips / iconos / colores reflejan qué detectó cada capacidad.
import type { CSSProperties } from "react";
import type { CapabilityEntry } from "../api/client";
import {
  ENTITY_TYPE_COLORS,
  VEHICLE_TYPE_COLORS,
} from "../colors/entityColors.gen";
import { ENTITY_LABELS, summarizeCapabilityChips } from "../labels";
import type { SessionStatus } from "../state/session";
import type { PerceptionEvent } from "../types/timonel.gen";
import { CapIcon } from "./CapIcon";

interface CapabilityDef {
  entityType: string;
}

/** Base = core default; Bajo demanda = opt-in / profile full. */
const GROUPS: { title: string; items: CapabilityDef[] }[] = [
  {
    title: "Base",
    items: [{ entityType: "object" }, { entityType: "face" }],
  },
  {
    title: "Bajo demanda",
    items: [
      { entityType: "pose" },
      { entityType: "vehicle" },
      { entityType: "text" },
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

/** Durante processing, hits parciales (ingest final=false) ya cuentan como hit. */
function capState(
  status: SessionStatus,
  available: boolean,
  count: number,
): CapState {
  if (!available) return "unavailable";
  if (isAnalyzing(status)) {
    if (count > 0) return "hit";
    return "pending";
  }
  if (!analysisComplete(status)) return "unavailable";
  return count > 0 ? "hit" : "miss";
}

function entityAccent(entityType: string): string {
  if (ENTITY_TYPE_COLORS[entityType]) return ENTITY_TYPE_COLORS[entityType];
  if (entityType === "vehicle") return VEHICLE_TYPE_COLORS.vehicle ?? "#ff5050";
  if (entityType === "object") return VEHICLE_TYPE_COLORS.car ?? "#00a0ff";
  return "#8a9bb0";
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

  const availableTypes = GROUPS.flatMap((g) => g.items)
    .map((i) => i.entityType)
    .filter((t) => catalog[t]?.available === true);

  const hitCount = availableTypes.filter((t) => (counts.get(t) ?? 0) > 0).length;
  const missCount = analysisComplete(status)
    ? availableTypes.filter((t) => (counts.get(t) ?? 0) === 0).length
    : 0;
  const complete = analysisComplete(status);
  const hasHits = hitCount > 0;
  const canShowHits = hasHits && (complete || isAnalyzing(status));

  return (
    <div className="tm-capability-panel">
      <div className="tm-cap-legend">
        <span title="Solo ocultar/mostrar cajas y etiquetas (sin reanalizar)">
          <EyeIcon /> mostrar / ocultar
        </span>
        {(complete || hasHits) && (
          <span
            className="tm-cap-summary"
            title="Hits vs sin datos en capacidades disponibles"
          >
            {hitCount} con hits
            {complete ? ` · ${missCount} sin datos` : " · …"}
          </span>
        )}
      </div>
      <div className="tm-cap-actions">
        <button
          type="button"
          className="tm-cap-action"
          disabled={!canShowHits}
          onClick={onShowHits}
        >
          Mostrar hits
        </button>
        <button
          type="button"
          className="tm-cap-action"
          disabled={!hasHits}
          onClick={onHideAll}
        >
          Ocultar todo
        </button>
      </div>
      {GROUPS.map((group) => {
        const visibleItems = group.items.filter(
          (item) => catalog[item.entityType]?.available === true,
        );
        if (visibleItems.length === 0) return null;
        return (
          <div className="tm-capability-group" key={group.title}>
            <div className="tm-capability-group-title">{group.title}</div>
            {visibleItems.map((item) => {
              const entry = catalog[item.entityType];
              const inferenceOn = entry?.active === true;
              const label = ENTITY_LABELS[item.entityType] ?? item.entityType;
              const count = counts.get(item.entityType) ?? 0;
              const state = inferenceOn
                ? capState(status, true, count)
                : ("unavailable" as CapState);
              const visibleChecked = visibility[item.entityType] === true;
              const canToggle = state === "hit";
              const accent = entityAccent(item.entityType);
              const { chips, extra } =
                state === "hit"
                  ? summarizeCapabilityChips(item.entityType, events)
                  : { chips: [] as string[], extra: 0 };
              const labelText =
                state === "hit" ? `${label} · ${count}` : label;
              const activeLayer = canToggle && visibleChecked;
              const itemStyle = {
                ["--tm-cap-accent" as string]: accent,
              } as CSSProperties;

              return (
                <div
                  key={item.entityType}
                  className={`tm-capability-item tm-cap-${inferenceOn ? state : "standby"}${activeLayer ? " tm-cap-layer-on" : ""}`}
                  style={itemStyle}
                >
                  <span className="tm-capability-icon" style={{ color: accent }}>
                    <CapIcon entityType={item.entityType} color={accent} />
                  </span>
                  <div className="tm-capability-body">
                    <span className="tm-capability-label">{labelText}</span>
                    {chips.length > 0 && (
                      <div className="tm-cap-chips">
                        {chips.map((chip) => (
                          <span
                            key={chip}
                            className="tm-cap-chip"
                            style={{ borderColor: accent, color: accent }}
                          >
                            {chip}
                          </span>
                        ))}
                        {extra > 0 && (
                          <span className="tm-cap-chip tm-cap-chip-more">
                            +{extra}
                          </span>
                        )}
                      </div>
                    )}
                    {!inferenceOn && onActivate && (
                      <button
                        type="button"
                        className="tm-cap-activate"
                        onClick={() => onActivate(item.entityType)}
                        title="Prender esta capa y re-analizar la misma foto"
                      >
                        Prender
                      </button>
                    )}
                  </div>
                  {inferenceOn ? (
                    <>
                      <span
                        className={`tm-cap-status tm-cap-status-${state}`}
                        style={
                          state === "hit" ? { background: accent } : undefined
                        }
                        aria-hidden
                      />
                      <button
                        type="button"
                        className={`tm-eye${!visibleChecked || !canToggle ? " off" : ""}`}
                        disabled={!canToggle}
                        title={
                          canToggle
                            ? visibleChecked
                              ? "Ocultar cajas"
                              : "Mostrar cajas"
                            : "Sin detecciones"
                        }
                        aria-label={`${label} visible`}
                        aria-pressed={canToggle && visibleChecked}
                        onClick={() =>
                          onToggleVisible(item.entityType, !visibleChecked)
                        }
                      >
                        <EyeIcon off={!canToggle || !visibleChecked} />
                      </button>
                    </>
                  ) : (
                    <span
                      className="tm-cap-status tm-cap-status-standby"
                      title="Disponible — prendelá para re-analizar"
                      aria-hidden
                    />
                  )}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
