// AnalyticsRow — agregados client-side sobre eventos VISIBLES.
// Charts universales siempre; dominio vehículo solo con hits; empty-states honestos.
import { useMemo } from "react";
import type { CapabilityEntry } from "../api/client";
import {
  ENTITY_TYPE_COLORS,
  VEHICLE_TYPE_COLORS,
} from "../colors/entityColors.gen";
import { ENTITY_LABELS } from "../labels";
import type { PerceptionEvent } from "../types/timonel.gen";
import { countCrossCapOverlaps } from "../utils/crossCapOverlaps";
import { EChart } from "./EChart";

interface Props {
  events: PerceptionEvent[];
  visibility: Record<string, boolean>;
  catalog: Record<string, CapabilityEntry>;
  analysisComplete: boolean;
}

function isVisible(event: PerceptionEvent, visibility: Record<string, boolean>): boolean {
  return visibility[event.entity_type] === true;
}

function entityColor(entityType: string): string {
  return ENTITY_TYPE_COLORS[entityType] ?? VEHICLE_TYPE_COLORS[entityType] ?? "#3f9bff";
}

const ACCENT = "#3f9bff";
const ACCENT_DIM = "#1e2f45";

export function AnalyticsRow({
  events,
  visibility,
  catalog,
  analysisComplete,
}: Props) {
  const visibleEvents = useMemo(
    () => events.filter((e) => isVisible(e, visibility)),
    [events, visibility],
  );

  const availableTypes = useMemo(
    () => Object.entries(catalog).filter(([, c]) => c.available).map(([t]) => t),
    [catalog],
  );
  const availableCapCount = availableTypes.length;

  const vehicleEvents = useMemo(
    () => visibleEvents.filter((e) => e.entity_type === "vehicle"),
    [visibleEvents],
  );

  const hasVehicleHitsInBuffer = useMemo(
    () => events.some((e) => e.entity_type === "vehicle"),
    [events],
  );

  const textAvailable = catalog.text?.available === true;
  const hasTextHitsInBuffer = useMemo(
    () => events.some((e) => e.entity_type === "text"),
    [events],
  );

  const overlaps = useMemo(
    () => countCrossCapOverlaps(visibleEvents, 0.3),
    [visibleEvents],
  );

  const stats = useMemo(() => {
    const byEntity = new Map<string, number>();
    let confSum = 0;
    for (const e of visibleEvents) {
      byEntity.set(e.entity_type, (byEntity.get(e.entity_type) ?? 0) + 1);
      confSum += e.confidence;
    }
    const uniquePlates = new Set(
      vehicleEvents
        .map((e) => (e.payload as { plate_text?: string | null }).plate_text)
        .filter((p): p is string => Boolean(p)),
    );
    return {
      total: visibleEvents.length,
      capHits: byEntity.size,
      meanConf: visibleEvents.length > 0 ? confSum / visibleEvents.length : null,
      byEntity,
      uniquePlates: uniquePlates.size,
    };
  }, [visibleEvents, vehicleEvents]);

  const byCapOption = useMemo(() => {
    const entries = [...stats.byEntity.entries()].sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...entries.map(([, v]) => v));
    return {
      title: {
        text: "Detecciones por capacidad",
        left: "center",
        textStyle: { fontSize: 12, color: "#8394a4" },
      },
      tooltip: { trigger: "axis" },
      grid: { left: 72, right: 36, top: 36, bottom: 16 },
      xAxis: { type: "value", show: false, max },
      yAxis: {
        type: "category",
        data: entries.map(([k]) => ENTITY_LABELS[k] ?? k).reverse(),
        axisLabel: { fontSize: 11, color: "#8394a4" },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [
        {
          type: "bar",
          data: entries
            .map(([k, v]) => ({
              value: v,
              itemStyle: { color: entityColor(k), borderRadius: [0, 4, 4, 0] },
            }))
            .reverse(),
          label: {
            show: true,
            position: "right",
            color: "#e7eef6",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
          },
          barWidth: 14,
        },
      ],
    };
  }, [stats.byEntity]);

  const confidenceOption = useMemo(() => {
    // Buckets 0.5–0.6 … 0.9–1.0 (5 bins).
    const buckets = [0, 0, 0, 0, 0];
    const binLabels = ["0.5–0.6", "0.6–0.7", "0.7–0.8", "0.8–0.9", "0.9–1.0"];
    for (const e of visibleEvents) {
      const c = Math.min(1, Math.max(0, e.confidence));
      const idx = Math.min(4, Math.max(0, Math.floor((c - 0.5) / 0.1)));
      if (c < 0.5) buckets[0] += 1;
      else buckets[idx] += 1;
    }
    return {
      title: {
        text: "Distribución de confianza",
        left: "center",
        textStyle: { fontSize: 12, color: "#8394a4" },
      },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const items = Array.isArray(params) ? params : [params];
          const first = items[0] as { dataIndex?: number; value?: number } | undefined;
          const i = first?.dataIndex ?? 0;
          const n = Number(first?.value ?? 0);
          return `Confianza ${binLabels[i]}: ${n} detección${n === 1 ? "" : "es"}`;
        },
      },
      grid: { left: 48, right: 16, top: 40, bottom: 44 },
      xAxis: {
        type: "category",
        name: "Confianza",
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: { color: "#8394a4", fontSize: 11 },
        data: binLabels,
        axisLabel: { fontSize: 9, color: "#5c6b7a", rotate: 0 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#223040" } },
      },
      yAxis: {
        type: "value",
        name: "Detecciones",
        nameLocation: "middle",
        nameGap: 32,
        nameTextStyle: { color: "#8394a4", fontSize: 11 },
        minInterval: 1,
        splitLine: { lineStyle: { color: "#1a2530" } },
        axisLabel: { color: "#5c6b7a", fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: buckets.map((v, i) => ({
            value: v,
            itemStyle: {
              color: i >= 3 ? ACCENT : ACCENT_DIM,
              borderColor: ACCENT,
              borderWidth: 1,
              borderRadius: [3, 3, 0, 0],
            },
          })),
          barWidth: "55%",
        },
      ],
    };
  }, [visibleEvents]);

  const vehicleTypeOption = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of vehicleEvents) {
      const vt =
        (e.payload as { vehicle_type?: string | null }).vehicle_type || "desconocido";
      counts.set(vt, (counts.get(vt) ?? 0) + 1);
    }
    const data = [...counts.entries()].map(([name, value]) => ({
      name,
      value,
      itemStyle: { color: VEHICLE_TYPE_COLORS[name.toLowerCase()] },
    }));
    return {
      title: {
        text: "Tipo de vehículo",
        left: "center",
        textStyle: { fontSize: 12, color: "#8394a4" },
      },
      tooltip: { trigger: "item" },
      series: [{ type: "pie", radius: ["35%", "70%"], data }],
    };
  }, [vehicleEvents]);

  const colorOption = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of vehicleEvents) {
      const color = (e.payload as { color?: string | null }).color || "desconocido";
      counts.set(color, (counts.get(color) ?? 0) + 1);
    }
    const entries = [...counts.entries()];
    return {
      title: {
        text: "Color",
        left: "center",
        textStyle: { fontSize: 12, color: "#8394a4" },
      },
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 12, top: 36, bottom: 28 },
      xAxis: {
        type: "category",
        data: entries.map(([k]) => k),
        axisLabel: { color: "#8394a4", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        splitLine: { lineStyle: { color: "#1a2530" } },
        axisLabel: { color: "#5c6b7a" },
      },
      series: [
        {
          type: "bar",
          data: entries.map(([, v]) => v),
          itemStyle: { color: ACCENT },
        },
      ],
    };
  }, [vehicleEvents]);

  const overlapTitle =
    overlaps.pairs.length > 0
      ? overlaps.pairs
          .map((p) => `${p.a} ∩ ${p.b} (${p.iou.toFixed(2)})`)
          .join(" · ")
      : "Sin solapes cross-capability (IoU ≥ 0.3)";

  // Hay eventos pero ninguno visible → empty de analítica.
  if (events.length > 0 && visibleEvents.length === 0) {
    return (
      <div className="tm-analytics-row">
        <div className="tm-domain">
          <div className="tm-domain-ic">◉</div>
          <div>
            <b>Nada visible en el canvas</b>
            <p>
              Prendé un ojo en Capacidades para ver detecciones y armar la
              analítica.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return null;
  }

  const showVehicleDomain = vehicleEvents.length > 0;
  const showVehicleEmpty =
    analysisComplete &&
    !hasVehicleHitsInBuffer &&
    catalog.vehicle?.available === true;
  const showTextEmpty =
    analysisComplete && textAvailable && !hasTextHitsInBuffer;

  return (
    <div className="tm-analytics-row">
      <div className="tm-kpis">
        <div className="tm-kpi">
          <div className="tm-kpi-v">{stats.total}</div>
          <div className="tm-kpi-l">Detecciones visibles</div>
        </div>
        <div className="tm-kpi">
          <div className="tm-kpi-v">
            {stats.capHits}
            <small>
              {" "}
              / {availableCapCount || "—"}
            </small>
          </div>
          <div className="tm-kpi-l">Capacidades con hits</div>
        </div>
        <div className="tm-kpi">
          <div className="tm-kpi-v">
            {stats.meanConf !== null ? stats.meanConf.toFixed(2) : "—"}
          </div>
          <div className="tm-kpi-l">Confianza media</div>
        </div>
        <div className="tm-kpi" title={overlapTitle}>
          <div className="tm-kpi-v">{overlaps.count}</div>
          <div className="tm-kpi-l">Solapes cross-capability</div>
        </div>
      </div>

      <div className="tm-charts">
        <div className="tm-chart">
          <EChart option={byCapOption} height={200} />
        </div>
        <div className="tm-chart">
          <EChart option={confidenceOption} height={200} />
        </div>
      </div>

      {showVehicleDomain && (
        <>
          <div className="tm-kpis tm-kpis-domain">
            <div className="tm-kpi">
              <div className="tm-kpi-v">{stats.uniquePlates}</div>
              <div className="tm-kpi-l">Patentes únicas</div>
            </div>
          </div>
          <div className="tm-charts tm-charts-domain">
            <div className="tm-chart">
              <EChart option={vehicleTypeOption} height={200} />
            </div>
            <div className="tm-chart">
              <EChart option={colorOption} height={200} />
            </div>
          </div>
        </>
      )}

      {showVehicleEmpty && (
        <div className="tm-domain">
          <div className="tm-domain-ic">⌀</div>
          <div>
            <b>Sin vehículos en esta imagen</b>
            <p>
              Los análisis de tipo, color y patente aparecen cuando la capacidad{" "}
              <b>Vehículo</b> detecta algo. Acá no hubo hits, así que se ocultan
              en vez de mostrar un gráfico vacío.
            </p>
          </div>
        </div>
      )}

      {showTextEmpty && (
        <div className="tm-domain">
          <div className="tm-domain-ic">T</div>
          <div>
            <b>Sin texto / patente OCR en esta imagen</b>
            <p>
              La capacidad <b>Texto</b> está disponible pero no hubo hits en este
              frame.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
