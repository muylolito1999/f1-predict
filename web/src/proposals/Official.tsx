import { useEffect, useMemo, useRef, useState } from "react";
import Switcher from "./Switcher";
import { DEMO, RACE_DRIVERS } from "./demoData";
import { annotateCalendar, type CalendarRace } from "./calendar2026";
import { activeSteps, totalDuration, type PipelineStep } from "./progressModel";
import type { PredictResponse } from "../types";

type Status = "idle" | "running" | "done" | "error";

const TEAM_HEX: Record<string, string> = {
  "Red Bull Racing": "#1e2d5f",
  McLaren: "#ff6400",
  Ferrari: "#dc0000",
  Mercedes: "#00a39a",
  Williams: "#00a3ff",
  "Aston Martin": "#1a4d3a",
  Alpine: "#0076b6",
  Haas: "#b6babd",
  "Kick Sauber": "#52e252",
  "Racing Bulls": "#4a7ad2",
};

function teamHex(team: string): string {
  return TEAM_HEX[team] ?? "#666";
}

function driverNumber(id: string): number {
  return RACE_DRIVERS.find((d) => d.id === id)?.number ?? 0;
}

function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

function Roundel({ num, bg }: { num: number; bg: string }) {
  return (
    <div
      style={{
        width: 42,
        height: 42,
        borderRadius: "50%",
        background: bg,
        color: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Bebas Neue', sans-serif",
        fontSize: 22,
        letterSpacing: 1,
        border: "2px solid #15151e",
        flexShrink: 0,
      }}
    >
      {num}
    </div>
  );
}

function PositionSpark({ hist, predicted, color, width = 160, height = 26 }: {
  hist: number[]; predicted: number; color: string; width?: number; height?: number;
}) {
  const max = Math.max(...hist) || 1;
  const barW = width / hist.length;
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <rect x={0} y={0} width={width} height={height} fill="rgba(225, 6, 0, 0.04)" />
      {hist.map((c, i) => {
        const h = (c / max) * (height - 2);
        const isPred = i + 1 === predicted;
        return (
          <rect
            key={i}
            x={i * barW}
            y={height - h}
            width={Math.max(1, barW - 0.4)}
            height={h}
            fill={isPred ? "#fff" : color}
            opacity={isPred ? 1 : 0.85}
          />
        );
      })}
    </svg>
  );
}

/** Try to hit the real backend; fall back to the demo dataset after a delay. */
async function runBackendOrDemo(req: {
  year: number; race: number; fp_sessions: string[]; skip_news: boolean; skip_weather: boolean;
}): Promise<{ response: PredictResponse; isDemo: boolean }> {
  try {
    const r = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = (await r.json()) as PredictResponse;
    return { response: data, isDemo: false };
  } catch {
    // Fall back to the bundled demo
    await new Promise((ok) => setTimeout(ok, 300));
    return { response: DEMO, isDemo: true };
  }
}

export default function Official() {
  const calendar = useMemo(() => annotateCalendar(new Date()), []);
  const nextIdx = calendar.findIndex((r) => r.status === "next");
  const [selected, setSelected] = useState<CalendarRace>(
    calendar[nextIdx >= 0 ? nextIdx : 0],
  );
  const [options, setOptions] = useState({
    skipNews: true,
    skipWeather: true,
    fpSessions: ["FP1", "FP2", "FP3"],
  });

  const [status, setStatus] = useState<Status>("idle");
  const [stepIdx, setStepIdx] = useState(-1);
  const [stepProgress, setStepProgress] = useState(0); // 0..1 of current step
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [selectedDriver, setSelectedDriver] = useState<string | null>(null);
  const apiPromise = useRef<Promise<{ response: PredictResponse; isDemo: boolean }> | null>(null);

  const steps: PipelineStep[] = useMemo(
    () => activeSteps(options),
    [options],
  );
  const totalMs = useMemo(() => totalDuration(steps), [steps]);

  // Step animator — ticks every 60ms, advances through steps.
  useEffect(() => {
    if (status !== "running" || startedAt == null) return;
    let raf = 0;
    const tick = () => {
      const now = performance.now();
      const sinceStart = now - startedAt;
      setElapsed(sinceStart);

      let cumulative = 0;
      let active = -1;
      for (let i = 0; i < steps.length; i++) {
        if (sinceStart < cumulative + steps[i].estMs) {
          active = i;
          setStepProgress(Math.min(1, (sinceStart - cumulative) / steps[i].estMs));
          break;
        }
        cumulative += steps[i].estMs;
      }

      if (active === -1) {
        // Past the end — wait for API.
        setStepIdx(steps.length - 1);
        setStepProgress(1);
      } else {
        setStepIdx(active);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [status, startedAt, steps]);

  async function runPrediction() {
    if (status === "running") return;
    setResult(null);
    setSelectedDriver(null);
    setIsDemo(false);
    setStatus("running");
    setStepIdx(0);
    setStepProgress(0);
    setElapsed(0);
    setStartedAt(performance.now());

    apiPromise.current = runBackendOrDemo({
      year: 2026,
      race: selected.round,
      fp_sessions: options.fpSessions,
      skip_news: options.skipNews,
      skip_weather: options.skipWeather,
    });

    const minDisplay = Math.min(totalMs, 14000);
    const [{ response, isDemo: demo }] = await Promise.all([
      apiPromise.current,
      new Promise((ok) => setTimeout(ok, minDisplay)),
    ]);

    setResult(response);
    setIsDemo(demo);
    setStepIdx(steps.length);
    setStepProgress(1);
    setStatus("done");
    setSelectedDriver(response.predictions[0]?.driver_id ?? null);
  }

  const selectedRow = result?.predictions.find((p) => p.driver_id === selectedDriver) ?? null;
  const selectedShap = selectedDriver ? (result?.shap_by_driver?.[selectedDriver] ?? []).slice(0, 6) : [];

  return (
    <>
      <style>{officialCSS}</style>
      <Switcher bg="#15151e" fg="#fff" border="#2a2a36" accent="#e10600" />

      <div className="f1">
        {/* Livery stripe */}
        <div className="livery">
          <span style={{ background: "#00a3ff" }} />
          <span style={{ background: "#ff6400" }} />
          <span style={{ background: "#dc0000" }} />
          <span style={{ background: "#1a4d3a" }} />
          <span style={{ background: "#15151e" }} />
        </div>

        {/* Top nav */}
        <header className="topnav">
          <div className="topnav-inner">
            <div className="brand">
              <span className="brand-mark">F1</span>
              <span className="brand-sep">·</span>
              <span className="brand-name">PREDICT</span>
              <span className="brand-year">2026</span>
            </div>
            <nav className="nav-tabs">
              <a className="on" href="#">Predict</a>
              <a href="#">Calendar</a>
              <a href="#">Standings</a>
              <a href="#">How it works</a>
            </nav>
            <div className="top-meta">
              <span className="pill live">
                <span className="dot" /> PRE-RACE
              </span>
            </div>
          </div>
        </header>

        {/* Section title */}
        <div className="section-intro">
          <div className="ann">
            <span className="ann-eyebrow">Formula 1 · 2026 World Championship</span>
            <h1 className="ann-title">Race Prediction</h1>
            <p className="ann-lede">
              Pick any round from the 2026 calendar. The model pulls free-practice
              telemetry, weather, and upgrade news, then runs 5,000 Monte-Carlo
              races to tell you who ends up where — and why.
            </p>
          </div>
        </div>

        {/* Calendar strip */}
        <section className="calendar-section">
          <div className="sec-head">
            <span className="sec-label">Calendar</span>
            <span className="sec-rule" />
            <span className="sec-hint">{calendar.length} rounds · click to select</span>
          </div>
          <div className="cal-strip" role="listbox">
            {calendar.map((r) => {
              const isSel = r.round === selected.round;
              return (
                <button
                  key={r.round}
                  className={`cal-card ${r.status ?? ""} ${isSel ? "sel" : ""}`}
                  onClick={() => setSelected(r)}
                  disabled={status === "running"}
                >
                  <div className="cal-top">
                    <span className="cal-round">R{r.round.toString().padStart(2, "0")}</span>
                    {r.status === "next" && <span className="cal-badge next">NEXT</span>}
                    {r.status === "past" && <span className="cal-badge past">DONE</span>}
                  </div>
                  <div className="cal-flag">{r.flag}</div>
                  <div className="cal-country">{r.country.toUpperCase()}</div>
                  <div className="cal-city">{r.city}</div>
                  <div className="cal-date">
                    {new Date(r.date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                  </div>
                  {isSel && <span className="cal-bar" />}
                </button>
              );
            })}
          </div>
        </section>

        {/* Hero */}
        <section className="hero">
          <div className="hero-bg" />
          <div className="hero-inner">
            <div className="hero-left">
              <div className="hero-eyebrow">
                ROUND {selected.round.toString().padStart(2, "0")} · {selected.country.toUpperCase()}
              </div>
              <h2 className="hero-title">
                {selected.name.replace(" Grand Prix", "").toUpperCase()}
                <em>GRAND PRIX</em>
              </h2>
              <div className="hero-meta">
                <div>
                  <span className="mk">Circuit</span>
                  <span className="mv">{selected.circuit}</span>
                </div>
                <div>
                  <span className="mk">Race date</span>
                  <span className="mv">
                    {new Date(selected.date).toLocaleDateString("en-GB", {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </span>
                </div>
                <div>
                  <span className="mk">Track</span>
                  <span className="mv">
                    {selected.length.toFixed(3)} km · {selected.laps} laps
                  </span>
                </div>
              </div>

              <div className="options">
                <label className="opt">
                  <input
                    type="checkbox"
                    checked={!options.skipNews}
                    onChange={(e) => setOptions({ ...options, skipNews: !e.target.checked })}
                  />
                  <span>Include news / upgrade analysis</span>
                  <small>+7s · Azure OpenAI</small>
                </label>
                <label className="opt">
                  <input
                    type="checkbox"
                    checked={!options.skipWeather}
                    onChange={(e) => setOptions({ ...options, skipWeather: !e.target.checked })}
                  />
                  <span>Include weather forecast</span>
                  <small>+2s · OpenWeatherMap</small>
                </label>
              </div>

              <button
                className="cta"
                disabled={status === "running"}
                onClick={runPrediction}
              >
                {status === "running" ? (
                  <>
                    <span className="cta-spinner" />
                    PREDICTING… {formatTime(elapsed)}
                  </>
                ) : status === "done" ? (
                  "RE-RUN PREDICTION"
                ) : (
                  <>
                    PREDICT THIS RACE
                    <span className="cta-arrow">→</span>
                  </>
                )}
              </button>

              {status === "done" && isDemo && (
                <div className="demo-flag">
                  Backend unreachable — showing bundled 2026 Bahrain demo.
                </div>
              )}
            </div>

            <div className="hero-right">
              <div className="track-card">
                <div className="track-card-title">TRACK PROFILE</div>
                <div className="track-card-num">{selected.round.toString().padStart(2, "0")}</div>
                <div className="track-card-body">
                  <div><span>Length</span><b>{selected.length.toFixed(3)} km</b></div>
                  <div><span>Laps</span><b>{selected.laps}</b></div>
                  <div><span>Distance</span><b>{(selected.length * selected.laps).toFixed(1)} km</b></div>
                  <div><span>Country</span><b>{selected.country}</b></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Progress panel — shows while running, folds up after */}
        {(status === "running" || status === "done") && (
          <section className={`progress-wrap ${status === "done" ? "done" : ""}`}>
            <div className="sec-head">
              <span className="sec-label">
                {status === "running" ? "Pipeline in progress" : "Pipeline complete"}
              </span>
              <span className="sec-rule" />
              <span className="sec-hint">
                {status === "running"
                  ? `elapsed ${formatTime(elapsed)} · estimated ${formatTime(totalMs)}`
                  : `total ${formatTime(elapsed)} · ${steps.length} steps`}
              </span>
            </div>

            <div className="progress-bar-outer">
              <div
                className="progress-bar-inner"
                style={{ width: `${Math.min(100, (elapsed / totalMs) * 100)}%` }}
              />
            </div>

            <ol className="step-list">
              {steps.map((s, i) => {
                const state =
                  status === "done" || i < stepIdx
                    ? "done"
                    : i === stepIdx
                    ? "active"
                    : "pending";
                return (
                  <li key={s.id} className={`step ${state}`}>
                    <span className="step-marker">
                      {state === "done" ? "✓" : state === "active" ? "●" : "○"}
                    </span>
                    <div className="step-body">
                      <div className="step-label">{s.label}</div>
                      <div className="step-detail">{s.detail}</div>
                      {state === "active" && (
                        <div className="step-progress">
                          <div style={{ width: `${stepProgress * 100}%` }} />
                        </div>
                      )}
                    </div>
                    <span className="step-eta">
                      {state === "done"
                        ? "DONE"
                        : state === "active"
                        ? `${Math.round(stepProgress * 100)}%`
                        : `~${formatTime(s.estMs)}`}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {/* Results */}
        {status === "done" && result && (
          <>
            <section className="results">
              <div className="sec-head">
                <span className="sec-label">Classification</span>
                <span className="sec-rule" />
                <span className="sec-hint">
                  Predicted order · Monte Carlo verified
                </span>
              </div>

              <div className="tbl-head">
                <span>Pos</span>
                <span>Driver</span>
                <span>Win</span>
                <span>Podium</span>
                <span>Points</span>
                <span>μ</span>
                <span>Range</span>
                <span>Distribution</span>
              </div>

              {result.predictions.map((p) => {
                const hist = result.position_histograms[p.driver_id];
                const color = teamHex(p.team);
                const num = driverNumber(p.driver_id);
                return (
                  <div
                    key={p.driver_id}
                    className={`tbl-row ${p.predicted_position <= 3 ? "podium" : ""} ${selectedDriver === p.driver_id ? "on" : ""}`}
                    onClick={() => setSelectedDriver(p.driver_id)}
                  >
                    <span className="tbl-pos">
                      {p.predicted_position.toString().padStart(2, "0")}
                    </span>
                    <div className="tbl-driver">
                      <Roundel num={num || 0} bg={color} />
                      <span className="tbl-stripe" style={{ background: color }} />
                      <div>
                        <div className="tbl-name">{p.driver_name}</div>
                        <div className="tbl-team">{p.team}</div>
                      </div>
                    </div>
                    <span className="tbl-stat">
                      <b>{(p.win_probability! * 100).toFixed(1)}%</b>
                      <small style={{ background: color }}>
                        <span style={{ width: `${Math.min(100, p.win_probability! * 100 * 2.5)}%` }} />
                      </small>
                    </span>
                    <span className="tbl-stat">
                      <b>{(p.podium_probability! * 100).toFixed(0)}%</b>
                      <small>
                        <span style={{ width: `${Math.min(100, p.podium_probability! * 100)}%`, background: "#00a3ff" }} />
                      </small>
                    </span>
                    <span className="tbl-stat">
                      <b>{(p.points_probability! * 100).toFixed(0)}%</b>
                      <small>
                        <span style={{ width: `${Math.min(100, p.points_probability! * 100)}%`, background: "#1a4d3a" }} />
                      </small>
                    </span>
                    <span className="tbl-mu">P{p.expected_position?.toFixed(1) ?? "—"}</span>
                    <span className="tbl-rng">
                      P{p.position_p10}–P{p.position_p90}
                    </span>
                    <span className="tbl-dist">
                      {hist && <PositionSpark hist={hist} predicted={p.predicted_position} color={color} />}
                    </span>
                  </div>
                );
              })}
            </section>

            <section className="analysis">
              <div className="sec-head">
                <span className="sec-label">Diagnostics</span>
                <span className="sec-rule" />
                <span className="sec-hint">Why the model chose this grid</span>
              </div>

              <div className="analysis-grid">
                <div className="card">
                  <div className="card-head">
                    <span className="card-title">Global feature weight</span>
                    <span className="card-sub">XGBoost · top 10</span>
                  </div>
                  {result.feature_importance.slice(0, 10).map((f) => (
                    <div key={f.feature} className="imp-row">
                      <div className="imp-name">{f.feature}</div>
                      <div className="imp-bar">
                        <span style={{ width: `${Math.min(100, f.pct * 5)}%` }} />
                      </div>
                      <div className="imp-val">{f.pct.toFixed(1)}%</div>
                    </div>
                  ))}
                </div>

                <div className="card">
                  <div className="card-head">
                    <span className="card-title">
                      SHAP · {selectedRow?.driver_name ?? "—"}
                    </span>
                    <span className="card-sub">
                      P{selectedRow?.predicted_position ?? "—"} · Click a driver above
                    </span>
                  </div>
                  {selectedShap.length === 0 ? (
                    <div className="empty">Select a driver in the classification.</div>
                  ) : (
                    selectedShap.map((s) => {
                      const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
                      return (
                        <div key={s.feature} className="shap-row">
                          <div className="shap-name">{s.feature}</div>
                          <div className="shap-bar">
                            {s.shap_value >= 0 ? (
                              <span className="pos" style={{ width: `${mag * 50}%` }} />
                            ) : (
                              <span className="neg" style={{ width: `${mag * 50}%` }} />
                            )}
                            <span className="mid" />
                          </div>
                          <div
                            className="shap-val"
                            style={{ color: s.shap_value >= 0 ? "#2ea043" : "#e10600" }}
                          >
                            {s.shap_value >= 0 ? "+" : ""}
                            {s.shap_value.toFixed(2)}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </section>
          </>
        )}

        <footer className="foot">
          <div>
            F1 PREDICT · 2026 Season
            <span className="sep">·</span>
            Ensemble (XGB / LGBM / CatBoost / Neural) + MC + SHAP
          </div>
          <div>
            {selected.round.toString().padStart(2, "0")} / {calendar.length}
            <span className="sep">·</span>
            {selected.country}
          </div>
        </footer>
      </div>
    </>
  );
}

const officialCSS = `
@import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@300;400;600;700;900&family=Bebas+Neue&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body { margin: 0; background: #0a0a11; color: #fff; }
.f1 {
  min-height: 100vh;
  background: #0a0a11;
  color: #fff;
  font-family: 'Titillium Web', 'DM Sans', sans-serif;
  padding-bottom: 80px;
}

.livery { display: flex; height: 6px; }
.livery span { flex: 1; }

/* TOP NAV */
.topnav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #15151e;
  border-bottom: 1px solid #24242f;
  backdrop-filter: blur(14px);
}
.topnav-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 14px 32px;
  display: flex;
  align-items: center;
  gap: 40px;
}
.brand { display: flex; align-items: baseline; gap: 8px; }
.brand-mark {
  background: #e10600;
  color: #fff;
  font-family: 'Titillium Web', sans-serif;
  font-weight: 900;
  font-style: italic;
  font-size: 26px;
  padding: 2px 10px 2px 8px;
  letter-spacing: -1px;
  clip-path: polygon(8% 0, 100% 0, 92% 100%, 0 100%);
}
.brand-sep { color: #4a4a5a; font-weight: 300; }
.brand-name {
  font-family: 'Titillium Web', sans-serif;
  font-weight: 700;
  letter-spacing: 4px;
  font-size: 13px;
}
.brand-year {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: #a9a9b8;
  letter-spacing: 2px;
  margin-left: 4px;
}
.nav-tabs {
  display: flex;
  gap: 4px;
  flex: 1;
}
.nav-tabs a {
  text-decoration: none;
  color: #c5c5d1;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  transition: color 150ms, background 150ms;
  border-radius: 2px;
}
.nav-tabs a:hover { color: #fff; background: rgba(255, 255, 255, 0.05); }
.nav-tabs a.on {
  color: #fff;
  position: relative;
}
.nav-tabs a.on::after {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 4px;
  height: 2px;
  background: #e10600;
}
.top-meta { display: flex; gap: 10px; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 1px solid #35353f;
  background: #1a1a24;
  border-radius: 2px;
}
.pill.live { color: #e10600; border-color: rgba(225, 6, 0, 0.4); background: rgba(225, 6, 0, 0.08); }
.pill .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #e10600;
  animation: f1-pulse 1.2s ease-in-out infinite;
}
@keyframes f1-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }

/* SECTION INTRO */
.section-intro {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 32px 40px;
}
.ann-eyebrow {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: #e10600;
}
.ann-title {
  font-family: 'Titillium Web', sans-serif;
  font-weight: 900;
  font-style: italic;
  font-size: clamp(56px, 7vw, 104px);
  line-height: 0.95;
  letter-spacing: -2px;
  margin: 12px 0 14px;
  text-transform: uppercase;
}
.ann-lede {
  max-width: 720px;
  font-size: 17px;
  color: #a9a9b8;
  line-height: 1.6;
  margin: 0;
}

/* SEC HEAD */
.sec-head {
  display: flex;
  align-items: center;
  gap: 18px;
  margin: 10px 0 18px;
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
  padding: 0 32px;
}
.sec-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: #e10600;
  white-space: nowrap;
  font-weight: 600;
}
.sec-rule { flex: 1; height: 1px; background: #24242f; }
.sec-hint {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #6a6a7a;
}

/* CALENDAR STRIP */
.calendar-section { margin-bottom: 60px; }
.cal-strip {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  gap: 10px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-padding-left: 32px;
  padding-bottom: 12px;
}
.cal-strip::-webkit-scrollbar { height: 4px; }
.cal-strip::-webkit-scrollbar-thumb { background: #24242f; }
.cal-card {
  flex: 0 0 144px;
  background: #15151e;
  border: 1px solid #24242f;
  border-radius: 2px;
  padding: 14px 12px 16px;
  cursor: pointer;
  scroll-snap-align: start;
  position: relative;
  transition: background 140ms, border-color 140ms, transform 140ms;
  font-family: inherit;
  color: #fff;
  text-align: left;
}
.cal-card:hover:not(:disabled) {
  background: #1a1a25;
  border-color: #35354a;
  transform: translateY(-2px);
}
.cal-card:disabled { opacity: 0.5; cursor: not-allowed; }
.cal-card.past { opacity: 0.5; }
.cal-card.sel {
  background: linear-gradient(180deg, #1a1a25 0%, #15151e 100%);
  border-color: #e10600;
}
.cal-card.sel::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0; width: 4px;
  background: #e10600;
}
.cal-bar { display: none; }
.cal-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.cal-round {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 2px;
  color: #a9a9b8;
  font-weight: 600;
}
.cal-badge {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 1.5px;
  padding: 2px 6px;
  border-radius: 1px;
  font-weight: 700;
}
.cal-badge.next { background: #e10600; color: #fff; }
.cal-badge.past { background: #2a2a36; color: #6a6a7a; }
.cal-flag { font-size: 30px; line-height: 1; margin-bottom: 8px; }
.cal-country {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 18px;
  letter-spacing: 1px;
  line-height: 1;
}
.cal-city {
  font-size: 12px;
  color: #a9a9b8;
  margin-top: 2px;
  font-weight: 500;
}
.cal-date {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  color: #6a6a7a;
  margin-top: 8px;
}

/* HERO */
.hero {
  max-width: 1400px;
  margin: 0 auto 60px;
  padding: 0 32px;
  position: relative;
}
.hero-bg {
  position: absolute;
  inset: 0;
  left: 32px;
  right: 32px;
  background:
    radial-gradient(ellipse at 80% 50%, rgba(225, 6, 0, 0.12), transparent 50%),
    linear-gradient(135deg, #15151e 0%, #0f0f17 100%);
  border-radius: 4px;
  z-index: 0;
}
.hero-inner {
  position: relative;
  z-index: 1;
  padding: 40px 40px 40px;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 40px;
  align-items: center;
}
@media (max-width: 900px) { .hero-inner { grid-template-columns: 1fr; } }

.hero-eyebrow {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 4px;
  color: #e10600;
  font-weight: 600;
  margin-bottom: 10px;
}
.hero-title {
  font-family: 'Bebas Neue', sans-serif;
  font-size: clamp(56px, 9vw, 140px);
  line-height: 0.85;
  letter-spacing: 0.5px;
  margin: 0 0 24px;
}
.hero-title em {
  display: block;
  font-style: normal;
  color: #e10600;
  font-size: 0.72em;
}
.hero-meta {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 24px;
  padding: 16px 0;
  border-top: 1px solid #24242f;
  border-bottom: 1px solid #24242f;
}
@media (max-width: 700px) { .hero-meta { grid-template-columns: 1fr; } }
.hero-meta .mk {
  display: block;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 2px;
  color: #6a6a7a;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.hero-meta .mv {
  font-family: 'Titillium Web', sans-serif;
  font-weight: 600;
  font-size: 15px;
  color: #fff;
}

.options {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 24px;
}
.opt {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #24242f;
  border-radius: 2px;
  cursor: pointer;
  font-size: 13px;
}
.opt:hover { border-color: #35354a; }
.opt input { accent-color: #e10600; cursor: pointer; }
.opt small {
  color: #6a6a7a;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 1px;
}

.cta {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  background: #e10600;
  color: #fff;
  padding: 16px 28px;
  border: 0;
  border-radius: 2px;
  font-family: 'Titillium Web', sans-serif;
  font-weight: 900;
  font-size: 14px;
  letter-spacing: 3px;
  cursor: pointer;
  transition: background 150ms, transform 150ms;
  clip-path: polygon(4% 0, 100% 0, 96% 100%, 0 100%);
  padding-left: 32px;
  padding-right: 36px;
}
.cta:hover:not(:disabled) { background: #ff1a0a; transform: translateX(2px); }
.cta:disabled { opacity: 0.7; cursor: not-allowed; }
.cta-arrow { font-size: 18px; line-height: 1; }
.cta-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: f1-spin 0.6s linear infinite;
}
@keyframes f1-spin { to { transform: rotate(360deg); } }

.demo-flag {
  margin-top: 14px;
  padding: 8px 12px;
  background: rgba(255, 176, 0, 0.08);
  border-left: 3px solid #ffb000;
  color: #ffb000;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  display: inline-block;
}

.track-card {
  background: rgba(225, 6, 0, 0.05);
  border: 1px solid rgba(225, 6, 0, 0.3);
  border-radius: 2px;
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
}
.track-card::after {
  content: '';
  position: absolute;
  right: -40px; top: -40px;
  width: 180px; height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(225, 6, 0, 0.2), transparent 70%);
}
.track-card-title {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 3px;
  color: #e10600;
  font-weight: 600;
  margin-bottom: 8px;
}
.track-card-num {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 110px;
  line-height: 0.8;
  color: #e10600;
  margin: 0 0 10px;
}
.track-card-body {
  display: grid;
  gap: 10px;
  position: relative;
  z-index: 2;
}
.track-card-body div {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.track-card-body span { color: #a9a9b8; font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 1px; }
.track-card-body b { font-weight: 700; }

/* PROGRESS */
.progress-wrap {
  max-width: 1400px;
  margin: 0 auto 60px;
  padding: 0 32px;
  transition: opacity 400ms;
}
.progress-wrap.done { opacity: 0.6; }
.progress-bar-outer {
  height: 3px;
  background: #1a1a24;
  margin: 0 32px 24px;
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
}
.progress-bar-inner {
  height: 100%;
  background: linear-gradient(90deg, #e10600 0%, #ff1a0a 100%);
  transition: width 120ms linear;
}
.step-list {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 32px;
  list-style: none;
  display: grid;
  gap: 2px;
}
.step {
  display: grid;
  grid-template-columns: 44px 1fr 90px;
  gap: 14px;
  padding: 14px 16px;
  background: #15151e;
  border-left: 3px solid #24242f;
  align-items: center;
  transition: background 180ms, border-color 180ms;
}
.step.active {
  background: rgba(225, 6, 0, 0.06);
  border-left-color: #e10600;
  animation: step-pulse 1.4s ease-in-out infinite;
}
@keyframes step-pulse {
  0%, 100% { background: rgba(225, 6, 0, 0.06); }
  50% { background: rgba(225, 6, 0, 0.12); }
}
.step.done {
  background: #10101a;
  border-left-color: #2ea043;
}
.step.pending { opacity: 0.45; }
.step-marker {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 18px;
  text-align: center;
  color: #6a6a7a;
}
.step.active .step-marker { color: #e10600; }
.step.done .step-marker { color: #2ea043; }
.step-label {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.3px;
}
.step-detail {
  font-size: 12px;
  color: #a9a9b8;
  margin-top: 2px;
  font-family: 'IBM Plex Mono', monospace;
  letter-spacing: 0.5px;
}
.step-progress {
  margin-top: 8px;
  height: 2px;
  background: rgba(225, 6, 0, 0.1);
  overflow: hidden;
}
.step-progress > div {
  height: 100%;
  background: #e10600;
  transition: width 120ms linear;
}
.step-eta {
  text-align: right;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 2px;
  color: #6a6a7a;
}
.step.active .step-eta { color: #e10600; font-weight: 700; }
.step.done .step-eta { color: #2ea043; }

/* RESULTS TABLE */
.results {
  max-width: 1400px;
  margin: 0 auto 60px;
  padding: 0 32px;
}
.tbl-head {
  display: grid;
  grid-template-columns: 70px 2.5fr 1fr 1fr 1fr 60px 90px 180px;
  gap: 14px;
  padding: 12px 16px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #6a6a7a;
  border-bottom: 2px solid #e10600;
  font-weight: 600;
}
.tbl-row {
  display: grid;
  grid-template-columns: 70px 2.5fr 1fr 1fr 1fr 60px 90px 180px;
  gap: 14px;
  padding: 14px 16px;
  align-items: center;
  border-bottom: 1px solid #1a1a24;
  cursor: pointer;
  transition: background 120ms, transform 120ms;
  position: relative;
}
.tbl-row:hover {
  background: rgba(225, 6, 0, 0.04);
}
.tbl-row.on {
  background: rgba(225, 6, 0, 0.08);
}
.tbl-row.on::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: #e10600;
}
.tbl-pos {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 42px;
  line-height: 0.9;
  letter-spacing: 1px;
  color: #fff;
}
.tbl-row.podium .tbl-pos { color: #e10600; }
.tbl-driver {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tbl-stripe { width: 3px; height: 36px; }
.tbl-name {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 22px;
  letter-spacing: 1px;
  line-height: 1;
}
.tbl-team {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 2px;
  color: #a9a9b8;
  text-transform: uppercase;
  margin-top: 4px;
}
.tbl-stat {
  display: block;
}
.tbl-stat b {
  font-family: 'Bebas Neue', sans-serif;
  font-weight: 400;
  font-size: 22px;
  letter-spacing: 0.5px;
  display: block;
  line-height: 1;
}
.tbl-stat small {
  display: block;
  height: 3px;
  background: #1a1a24;
  margin-top: 6px;
  position: relative;
}
.tbl-stat small span {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: #e10600;
}
.tbl-mu {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 22px;
  color: #ffb000;
}
.tbl-rng {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  letter-spacing: 1px;
  color: #a9a9b8;
}

/* ANALYSIS */
.analysis {
  max-width: 1400px;
  margin: 0 auto 60px;
  padding: 0 32px;
}
.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
@media (max-width: 900px) { .analysis-grid { grid-template-columns: 1fr; } }
.card {
  background: #15151e;
  border: 1px solid #24242f;
  border-radius: 2px;
  padding: 22px 26px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: 12px;
  margin-bottom: 16px;
  border-bottom: 1px solid #24242f;
}
.card-title {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 26px;
  letter-spacing: 1px;
}
.card-sub {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 2px;
  color: #6a6a7a;
  text-transform: uppercase;
}

.imp-row {
  display: grid;
  grid-template-columns: 1fr 70px;
  gap: 12px;
  padding: 10px 0;
  align-items: center;
  border-bottom: 1px solid #1a1a24;
}
.imp-row:last-child { border-bottom: 0; }
.imp-name {
  font-size: 13px;
  font-weight: 500;
  grid-column: 1 / 2;
  grid-row: 1 / 2;
}
.imp-bar {
  grid-column: 1 / 2;
  grid-row: 2 / 3;
  height: 4px;
  background: #1a1a24;
  margin-top: 4px;
}
.imp-bar > span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #e10600, #ff6400);
}
.imp-val {
  grid-column: 2 / 3;
  grid-row: 1 / 3;
  font-family: 'Bebas Neue', sans-serif;
  font-size: 22px;
  color: #e10600;
  text-align: right;
}

.shap-row {
  display: grid;
  grid-template-columns: 1fr 70px;
  gap: 12px;
  padding: 10px 0;
  align-items: center;
  border-bottom: 1px solid #1a1a24;
}
.shap-row:last-child { border-bottom: 0; }
.shap-name {
  font-size: 13px;
  font-weight: 500;
  grid-column: 1 / 2;
  grid-row: 1 / 2;
}
.shap-bar {
  grid-column: 1 / 2;
  grid-row: 2 / 3;
  height: 6px;
  background: #1a1a24;
  position: relative;
  margin-top: 4px;
}
.shap-bar .mid { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: rgba(255, 255, 255, 0.3); }
.shap-bar .pos { position: absolute; left: 50%; top: 0; bottom: 0; background: #2ea043; }
.shap-bar .neg { position: absolute; right: 50%; top: 0; bottom: 0; background: #e10600; }
.shap-val {
  grid-column: 2 / 3;
  grid-row: 1 / 3;
  font-family: 'Bebas Neue', sans-serif;
  font-size: 22px;
  text-align: right;
}
.empty {
  color: #6a6a7a;
  padding: 20px;
  text-align: center;
  font-size: 13px;
}

/* FOOTER */
.foot {
  max-width: 1400px;
  margin: 80px auto 0;
  padding: 24px 32px 0;
  border-top: 1px solid #24242f;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 2px;
  color: #6a6a7a;
  text-transform: uppercase;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.foot .sep { color: #e10600; margin: 0 10px; }

@media (max-width: 900px) {
  .tbl-head, .tbl-row {
    grid-template-columns: 60px 2fr 1fr 1fr;
  }
  .tbl-head > :nth-child(n+5), .tbl-row > :nth-child(n+5) { display: none; }
}
`;
