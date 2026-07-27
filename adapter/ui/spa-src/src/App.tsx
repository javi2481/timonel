// App — shell SPA: inferencia en background; toggles = solo visibilidad.
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCapabilities,
  type CapabilityEntry,
} from "./api/client";
import { AnalyticsRow } from "./components/AnalyticsRow";
import { CapabilityPanel } from "./components/CapabilityPanel";
import { EventsTable } from "./components/EventsTable";
import { Legend } from "./components/Legend";
import { PhotoCanvas } from "./components/PhotoCanvas";
import { UploadBar } from "./components/UploadBar";
import { useSession } from "./state/session";

export function App() {
  const { state, upload, clear, retry } = useSession();
  const [visibility, setVisibility] = useState<Record<string, boolean>>({});
  const [catalog, setCatalog] = useState<Record<string, CapabilityEntry>>({});
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const refreshCatalog = useCallback(async () => {
    try {
      const res = await getCapabilities();
      setCatalog(res.capabilities);
    } catch {
      // Adapter offline: keep last catalog.
    }
  }, []);

  useEffect(() => {
    void refreshCatalog();
  }, [refreshCatalog]);

  // Reset visibility on generation bump (opt-in → todo oculto).
  useEffect(() => {
    setVisibility({});
    setHoveredId(null);
    setSelectedId(null);
  }, [state.generation]);

  useEffect(() => {
    void refreshCatalog();
  }, [state.generation, refreshCatalog]);

  const availableCapCount = useMemo(
    () => Object.values(catalog).filter((c) => c.available).length,
    [catalog],
  );

  const hitEntityTypes = useMemo(() => {
    const present = new Set(state.events.map((e) => e.entity_type));
    return [...present];
  }, [state.events]);

  const onShowHits = useCallback(() => {
    setVisibility((prev) => {
      const next = { ...prev };
      for (const t of hitEntityTypes) next[t] = true;
      return next;
    });
  }, [hitEntityTypes]);

  const onHideAll = useCallback(() => {
    setVisibility({});
  }, []);

  return (
    <div className="vi-app">
      <header className="vi-header">
        <div className="vi-brand">
          <h1>Vision Intelligence</h1>
          <div className="vi-brand-sub">panel de percepción · /app</div>
        </div>
        <UploadBar
          status={state.status}
          errorMessage={state.errorMessage}
          onUpload={(file) => void upload(file)}
          onClear={() => void clear()}
          onRetry={retry}
        />
      </header>

      <div className="vi-layout">
        <aside className="vi-sidebar">
          <div className="vi-card-h">Capacidades</div>
          <CapabilityPanel
            events={state.events}
            visibility={visibility}
            catalog={catalog}
            status={state.status}
            onToggleVisible={(entityType, visible) =>
              setVisibility((prev) => ({ ...prev, [entityType]: visible }))
            }
            onShowHits={onShowHits}
            onHideAll={onHideAll}
          />
        </aside>

        <main className="vi-main">
          {state.status === "idle" ? (
            <div className="vi-empty-card">
              <strong>Sin foto activa</strong>
              <p>Subí una imagen para empezar el análisis.</p>
            </div>
          ) : (
            <>
              <PhotoCanvas
                generation={state.generation}
                events={state.events}
                visibility={visibility}
                hoveredId={hoveredId}
                selectedId={selectedId}
                onHover={setHoveredId}
                onSelect={setSelectedId}
                status={state.status}
                errorMessage={state.errorMessage}
                onRetry={retry}
                availableCapCount={availableCapCount}
              />
              <Legend events={state.events} visibility={visibility} />
            </>
          )}
        </main>
      </div>

      <AnalyticsRow events={state.events} visibility={visibility} />

      <EventsTable
        events={state.events}
        visibility={visibility}
        hoveredId={hoveredId}
        selectedId={selectedId}
        onHover={setHoveredId}
        onSelect={setSelectedId}
      />
    </div>
  );
}
