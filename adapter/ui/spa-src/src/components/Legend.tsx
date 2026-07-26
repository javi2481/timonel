// Legend — solo entity_types (y vehicle_types) presentes y visibles.
import {
  colorForTrackId,
  ENTITY_TYPE_COLORS,
  VEHICLE_TYPE_COLORS,
} from "../colors/entityColors.gen";
import { ENTITY_LABELS } from "../labels";
import type { PerceptionEvent } from "../types/epp.gen";

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
}

export function Legend({ events, visibility }: Props) {
  const visible = events.filter((e) => visibility[e.entity_type] !== false);
  if (visible.length === 0) return null;

  const types = new Set(visible.map((e) => e.entity_type));
  const vehicleTypes = new Set<string>();
  for (const e of visible) {
    if (e.entity_type !== "vehicle") continue;
    const vt = (e.payload as { vehicle_type?: string | null }).vehicle_type;
    if (vt) vehicleTypes.add(vt.toLowerCase());
  }

  const items: { key: string; label: string; color: string }[] = [];

  if (types.has("vehicle") && vehicleTypes.size > 0) {
    for (const vt of [...vehicleTypes].sort()) {
      items.push({
        key: `vehicle:${vt}`,
        label: vt,
        color: VEHICLE_TYPE_COLORS[vt] ?? colorForTrackId(vt),
      });
    }
  } else if (types.has("vehicle")) {
    items.push({
      key: "vehicle",
      label: ENTITY_LABELS.vehicle,
      color: VEHICLE_TYPE_COLORS.vehicle ?? ENTITY_TYPE_COLORS.vehicle ?? colorForTrackId("vehicle"),
    });
  }

  for (const t of [...types].sort()) {
    if (t === "vehicle") continue;
    items.push({
      key: t,
      label: ENTITY_LABELS[t] ?? t,
      color: ENTITY_TYPE_COLORS[t] ?? colorForTrackId(t),
    });
  }

  return (
    <div className="vi-legend-card">
      <div className="vi-legend-h">
        Leyenda <span className="vi-legend-hint">solo lo visible</span>
      </div>
      <div className="vi-legend">
        {items.map((it) => (
          <span className="vi-legend-it" key={it.key}>
            <span className="vi-legend-sw" style={{ background: it.color }} />
            {it.label}
          </span>
        ))}
      </div>
    </div>
  );
}
