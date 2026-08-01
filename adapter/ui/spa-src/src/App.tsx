// App — shell SPA: inferencia en background; toggles = solo visibilidad.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getCapabilities,
  putCapabilities,
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
  const autoShownGen = useRef<number | null>(null);

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
    autoShownGen.current = null;
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

  const analysisComplete =
    state.status === "ready" ||
    state.status === "degraded" ||
    state.status === "empty";

  // Una vez por generation al completar: prender ojos de lo que tuvo hits.
  useEffect(() => {
    if (!analysisComplete) return;
    if (autoShownGen.current === state.generation) return;
    if (hitEntityTypes.length === 0) {
      autoShownGen.current = state.generation;
      return;
    }
    autoShownGen.current = state.generation;
    setVisibility((prev) => {
      const next = { ...prev };
      for (const t of hitEntityTypes) next[t] = true;
      return next;
    });
  }, [analysisComplete, state.generation, hitEntityTypes]);

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

  const onActivate = useCallback(
    async (entityType: string) => {
      try {
        await putCapabilities({ [entityType]: true });
        await refreshCatalog();
      } catch {
        // Keep catalog; user can retry.
      }
    },
    [refreshCatalog],
  );

  return (
    <div className="tm-app">
      <header className="tm-header">
        <div className="tm-brand">
          <h1>Timonel</h1>
          <p className="tm-brand-sub">
            Usa PaddleX (modelos de visión open-source) para detectar objetos,
            caras, pose y texto en una foto, y mostrar todo junto en un solo
            panel.
          </p>
        </div>
        <UploadBar
          status={state.status}
          errorMessage={state.errorMessage}
          onUpload={(file) => void upload(file)}
          onClear={() => void clear()}
          onRetry={retry}
        />
      </header>

      {(state.status === "uploading" || state.status === "processing") && (
        <div
          className="tm-header-progress"
          role="progressbar"
          aria-busy="true"
          aria-label={
            state.status === "uploading" ? "Subiendo foto" : "Analizando detecciones"
          }
        >
          <div className="tm-progress-indeterminate" aria-hidden>
            <div className="tm-progress-indeterminate-bar" />
          </div>
        </div>
      )}

      <div className="tm-layout">
        <aside className="tm-sidebar">
          <div className="tm-card-h">Capacidades</div>
          <CapabilityPanel
            events={state.events}
            visibility={visibility}
            catalog={catalog}
            status={state.status}
            onToggleVisible={(entityType, visible) =>
              setVisibility((prev) => ({ ...prev, [entityType]: visible }))
            }
            onActivate={(entityType) => void onActivate(entityType)}
            onShowHits={onShowHits}
            onHideAll={onHideAll}
          />
        </aside>

        <main className="tm-main">
          {state.status === "idle" ? (
            <div className="tm-stage-idle" role="status">
              <div className="tm-stage-idle-inner">
                <h2 className="tm-stage-idle-title">Timonel</h2>
                <p className="tm-stage-idle-copy">
                  Timonel orquesta detectores PaddleX sobre una foto. Elegí una
                  imagen <code>demo_*.jpg</code> del selector (las marcadas core
                  andan sin profile full) o subí la tuya. Después prendé una capa
                  bajo demanda en el panel para re-analizar la misma foto.
                </p>
              </div>
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

      <AnalyticsRow
        events={state.events}
        visibility={visibility}
        catalog={catalog}
        analysisComplete={analysisComplete}
      />

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
