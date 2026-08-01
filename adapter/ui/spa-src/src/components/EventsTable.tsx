// EventsTable — tabla colapsable de PerceptionEvent visibles, sincronizada
// con el hover/selección de PhotoCanvas vía el mismo `eventId`.
import { useState } from "react";
import {
  ENTITY_TYPE_COLORS,
  VEHICLE_TYPE_COLORS,
} from "../colors/entityColors.gen";
import { describeEvent } from "../labels";
import type { PerceptionEvent } from "../types/timonel.gen";
import { eventId } from "../utils/eventId";

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  hoveredId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}

function pillStyle(entityType: string): { background: string; color: string } {
  const color =
    ENTITY_TYPE_COLORS[entityType] ??
    VEHICLE_TYPE_COLORS[entityType] ??
    "#3f9bff";
  return {
    background: `${color}26`,
    color,
  };
}

export function EventsTable({ events, visibility, hoveredId, selectedId, onHover, onSelect }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const rows = events
    .map((event, index) => ({ event, id: eventId(event, index) }))
    .filter(({ event }) => visibility[event.entity_type] === true);

  return (
    <div className="tm-events-table">
      <button className="tm-collapse-toggle" onClick={() => setCollapsed((v) => !v)}>
        {collapsed ? "▶" : "▼"} Eventos ({rows.length})
      </button>
      {!collapsed && (
        <table className="tm-table">
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Confianza</th>
              <th>Detalle</th>
              <th>Hora</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ event, id }) => (
              <tr
                key={id}
                className={
                  id === selectedId ? "tm-row-selected" : id === hoveredId ? "tm-row-hovered" : ""
                }
                onMouseEnter={() => onHover(id)}
                onMouseLeave={() => onHover(null)}
                onClick={() => onSelect(id === selectedId ? null : id)}
              >
                <td>
                  <span
                    className="tm-pill tm-pill-type"
                    style={pillStyle(event.entity_type)}
                  >
                    {event.entity_type}
                  </span>
                </td>
                <td className="tm-conf">{event.confidence.toFixed(2)}</td>
                <td>{describeEvent(event)}</td>
                <td>{new Date(event.occurred_at).toLocaleTimeString()}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="tm-muted">
                  Sin eventos visibles.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
