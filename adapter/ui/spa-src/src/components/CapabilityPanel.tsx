// CapabilityPanel — dual controls: visible (client) + active (server).
// visible: disabled when entity has no events. active: PUT /capabilities; vehicle locked.
import type { CapabilityEntry } from "../api/client";
import { ENTITY_LABELS } from "../labels";
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

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  catalog: Record<string, CapabilityEntry>;
  onToggleVisible: (entityType: string, visible: boolean) => void;
  onToggleActive: (entityType: string, active: boolean) => void;
}

export function CapabilityPanel({
  events,
  visibility,
  catalog,
  onToggleVisible,
  onToggleActive,
}: Props) {
  const present = new Set(events.map((e) => e.entity_type));

  return (
    <div className="vi-capability-panel">
      <div className="vi-cap-legend">
        <span title="Mostrar en la foto">
          <EyeIcon /> mostrar
        </span>
        <span title="Correr inferencia">⚡ inferencia</span>
      </div>
      {GROUPS.map((group) => (
        <div className="vi-capability-group" key={group.title}>
          <div className="vi-capability-group-title">{group.title}</div>
          {group.items.map((item) => {
            const label = ENTITY_LABELS[item.entityType] ?? item.entityType;
            const hasEvents = present.has(item.entityType);
            const visibleChecked = visibility[item.entityType] !== false;
            const entry = catalog[item.entityType];
            const available = entry?.available === true;
            const activeChecked = entry?.active === true;
            const critical = entry?.critical === true || item.entityType === "vehicle";
            const activeLocked = critical || !available;
            return (
              <div
                key={item.entityType}
                className={`vi-capability-item${!hasEvents && !available ? " vi-capability-disabled" : ""}`}
              >
                <span className="vi-capability-label">{label}</span>
                <button
                  type="button"
                  className={`vi-eye${!hasEvents || !visibleChecked ? " off" : ""}`}
                  disabled={!hasEvents}
                  title={hasEvents ? "Visible" : "sin detecciones"}
                  aria-label={`${label} visible`}
                  aria-pressed={hasEvents && visibleChecked}
                  onClick={() => onToggleVisible(item.entityType, !visibleChecked)}
                >
                  <EyeIcon off={!hasEvents || !visibleChecked} />
                </button>
                <button
                  type="button"
                  role="switch"
                  className={`vi-sw${activeChecked ? " on" : ""}${critical ? " locked" : ""}`}
                  disabled={activeLocked}
                  aria-checked={activeChecked}
                  aria-label={`${label} active`}
                  title={
                    critical
                      ? "Vehicle siempre activo"
                      : available
                        ? "Inferencia activa"
                        : "No disponible en este deploy"
                  }
                  onClick={() => {
                    if (!activeLocked) onToggleActive(item.entityType, !activeChecked);
                  }}
                  onKeyDown={(e) => {
                    if (activeLocked) return;
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      onToggleActive(item.entityType, !activeChecked);
                    }
                  }}
                />
                {!hasEvents && (
                  <em className="vi-capability-empty-hint">sin detecciones</em>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
