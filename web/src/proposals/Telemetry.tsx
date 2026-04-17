import { useEffect, useMemo, useState } from "react";
import Switcher from "./Switcher";
import { DEMO } from "./demoData";

/** Render a floating-point as right-padded fixed width. */
function fw(v: number | undefined, w: number, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—".padStart(w, " ");
  return v.toFixed(digits).padStart(w, " ");
}

function asciiBar(pct: number, width = 10): string {
  const blocks = "█▓▒░";
  const filled = Math.round((pct / 100) * width);
  return blocks[0].repeat(Math.max(0, Math.min(width, filled))) + "░".repeat(
    Math.max(0, width - Math.max(0, Math.min(width, filled))),
  );
}

function Spark({ hist, predicted, width = 140, height = 18 }: {
  hist: number[]; predicted: number; width?: number; height?: number;
}) {
  const max = Math.max(...hist) || 1;
  const barW = width / hist.length;
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {hist.map((c, i) => {
        const h = (c / max) * (height - 2);
        const isPred = i + 1 === predicted;
        return (
          <rect
            key={i}
            x={i * barW}
            y={height - h}
            width={barW - 0.4}
            height={h}
            fill={isPred ? "#ffb000" : "#00ff6a"}
            opacity={isPred ? 1 : 0.65}
          />
        );
      })}
    </svg>
  );
}

export default function Telemetry() {
  const { predictions, feature_importance, shap_by_driver, metadata, features_by_driver } = DEMO;
  const [selected, setSelected] = useState(predictions[0].driver_id);
  const [clock, setClock] = useState(0);
  const [cursorOn, setCursorOn] = useState(true);

  useEffect(() => {
    const t = setInterval(() => setClock((c) => c + 1), 100);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setCursorOn((c) => !c), 530);
    return () => clearInterval(t);
  }, []);

  const simsDone = Math.min(5000, 4200 + clock * 8);
  const selectedRow = predictions.find((p) => p.driver_id === selected)!;
  const selectedShap = shap_by_driver?.[selected] ?? [];
  const selectedFeatures = features_by_driver?.[selected] ?? {};

  const dnfRisk = useMemo(() => {
    // Approximate DNF probability as 1 - points_prob for bottom half + baseline
    return predictions
      .map((p) => ({
        id: p.driver_id,
        pct: Math.max(5, 15 - p.predicted_position * 0.4 + (p.predicted_position > 14 ? 6 : 0)),
      }))
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 4);
  }, [predictions]);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
        html, body { margin: 0; background: #000; }
        .tel {
          min-height: 100vh;
          background: #000;
          color: #00ff6a;
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 13px;
          line-height: 1.45;
          padding: 32px 24px 80px;
          position: relative;
          overflow-x: hidden;
        }
        .tel::before {
          content: '';
          position: fixed;
          inset: 0;
          pointer-events: none;
          background: repeating-linear-gradient(
            0deg,
            rgba(0, 255, 106, 0.03) 0,
            rgba(0, 255, 106, 0.03) 1px,
            transparent 1px,
            transparent 3px
          );
          z-index: 500;
        }
        .tel::after {
          content: '';
          position: fixed;
          inset: 0;
          pointer-events: none;
          background: radial-gradient(ellipse at center, transparent 50%, rgba(0, 0, 0, 0.55) 100%);
          z-index: 501;
        }
        .tel-inner {
          max-width: 1200px;
          margin: 0 auto;
          position: relative;
          z-index: 1;
        }

        .ribbon {
          display: flex;
          justify-content: space-between;
          border: 1px solid #00ff6a;
          padding: 6px 12px;
          margin-bottom: 22px;
          font-weight: 500;
          letter-spacing: 1px;
          text-transform: uppercase;
          font-size: 12px;
        }
        .ribbon .amber { color: #ffb000; }
        .ribbon .red { color: #ff0040; }
        .blink {
          animation: blink 0.9s steps(2, end) infinite;
        }
        @keyframes blink {
          0%, 50% { opacity: 1; }
          50.01%, 100% { opacity: 0; }
        }

        pre.ascii {
          margin: 0;
          font-family: inherit;
          font-size: 13px;
          line-height: 1.45;
          color: #00ff6a;
          white-space: pre;
        }

        .section-title {
          margin: 28px 0 10px;
          color: #00ff6a;
          font-weight: 600;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          font-size: 12px;
        }
        .section-title span { color: #ffb000; }

        .grid-wrap {
          border: 1px solid #00ff6a;
          padding: 10px 14px;
          background: linear-gradient(180deg, rgba(0, 255, 106, 0.02), transparent);
        }

        .tbl {
          width: 100%;
          font-family: inherit;
          border-collapse: collapse;
          font-size: 12.5px;
        }
        .tbl th {
          text-align: left;
          padding: 6px 8px;
          color: #8fffb8;
          font-weight: 500;
          border-bottom: 1px dashed rgba(0, 255, 106, 0.3);
          text-transform: uppercase;
          letter-spacing: 1px;
          font-size: 10px;
        }
        .tbl td {
          padding: 5px 8px;
          border-bottom: 1px dotted rgba(0, 255, 106, 0.15);
          vertical-align: middle;
        }
        .tbl tr:hover td { background: rgba(0, 255, 106, 0.06); cursor: pointer; }
        .tbl tr.selected td {
          background: rgba(255, 176, 0, 0.1);
          color: #ffb000;
        }
        .num { text-align: right; font-variant-numeric: tabular-nums; }
        .dim { color: rgba(0, 255, 106, 0.55); }
        .amber { color: #ffb000; }
        .red { color: #ff0040; }
        .bar { color: #00ff6a; letter-spacing: -0.5px; }

        .twocol {
          display: grid;
          grid-template-columns: 1fr 360px;
          gap: 22px;
          margin-top: 22px;
        }
        @media (max-width: 900px) { .twocol { grid-template-columns: 1fr; } }

        .box {
          border: 1px solid #00ff6a;
          padding: 10px 14px;
          background: rgba(0, 255, 106, 0.02);
        }
        .box h3 {
          margin: 0 0 10px;
          color: #00ff6a;
          font-weight: 600;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
        }
        .box h3 .tag { color: #ffb000; }

        .kv {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 2px 10px;
          font-size: 12px;
        }
        .kv .k { color: rgba(0, 255, 106, 0.65); }
        .kv .v { color: #00ff6a; font-variant-numeric: tabular-nums; text-align: right; }

        .alert {
          border: 1px solid #ff0040;
          color: #ff0040;
          padding: 10px 14px;
          background: rgba(255, 0, 64, 0.05);
          margin-bottom: 14px;
        }
        .alert h3 {
          margin: 0 0 6px;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #ff0040;
        }

        .shap-row {
          display: grid;
          grid-template-columns: 170px 1fr 60px;
          gap: 8px;
          align-items: center;
          font-size: 12px;
          padding: 3px 0;
        }
        .shap-row .track {
          height: 10px;
          background: rgba(0, 255, 106, 0.08);
          position: relative;
        }
        .shap-row .mid {
          position: absolute; top: 0; bottom: 0; left: 50%; width: 1px; background: rgba(0, 255, 106, 0.5);
        }
        .shap-row .fill-pos { position: absolute; left: 50%; top: 0; bottom: 0; background: #00ff6a; }
        .shap-row .fill-neg { position: absolute; right: 50%; top: 0; bottom: 0; background: #ff0040; }

        .picker {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-bottom: 10px;
        }
        .picker button {
          background: transparent;
          color: #00ff6a;
          border: 1px solid rgba(0, 255, 106, 0.4);
          padding: 3px 7px;
          font-family: inherit;
          font-size: 11px;
          cursor: pointer;
        }
        .picker button.on {
          background: #ffb000;
          border-color: #ffb000;
          color: #000;
        }

        .footer {
          margin-top: 40px;
          border-top: 1px solid rgba(0, 255, 106, 0.3);
          padding-top: 16px;
          font-size: 11px;
          color: rgba(0, 255, 106, 0.6);
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
        }
      `}</style>

      <Switcher bg="#000" fg="#00ff6a" border="#00ff6a" accent="#ffb000" />

      <div className="tel">
        <div className="tel-inner">
          <div className="ribbon">
            <span>
              ●&nbsp;&nbsp;LINK OK&nbsp;&nbsp;<span className="dim">│</span>&nbsp;&nbsp;PIT-WALL 4
            </span>
            <span>
              {metadata.race_name.toUpperCase()} · R{metadata.round} · {metadata.year}
            </span>
            <span>
              SIM {simsDone.toString().padStart(4, "0")}/5000&nbsp;&nbsp;
              <span className="amber">σ=0.25</span>&nbsp;
              <span className="blink">▋</span>
            </span>
          </div>

          <pre className="ascii">
{`┌─ PRE-RACE FORECAST ─────────────────────────────────────────────────────────┐
│ MODEL: ENS (XGB·LGBM·CATB·NET) + STACKER + MC·ISOTONIC·SHAP                 │
│ INPUTS: FP1 ✓ FP2 ✓ FP3 ✓ · WEATHER ✓ · UPGRADES ✓ · GRID → QUALI MODEL     │
│ CONFIDENCE: ${metadata.confidence.padEnd(4)}                                                            │
└─────────────────────────────────────────────────────────────────────────────┘`}
          </pre>

          <div className="section-title">═══ CLASSIFICATION <span>/ EXPECTED FINISH</span> ═══</div>
          <div className="grid-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>POS</th>
                  <th>DRV</th>
                  <th>DRIVER</th>
                  <th>TEAM</th>
                  <th className="num">WIN%</th>
                  <th className="num">POD%</th>
                  <th className="num">PTS%</th>
                  <th className="num">μPOS</th>
                  <th className="num">P10</th>
                  <th className="num">P90</th>
                  <th>DIST</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((p) => {
                  const hist = DEMO.position_histograms[p.driver_id];
                  return (
                    <tr
                      key={p.driver_id}
                      className={selected === p.driver_id ? "selected" : ""}
                      onClick={() => setSelected(p.driver_id)}
                    >
                      <td className="num">P{p.predicted_position.toString().padStart(2, "0")}</td>
                      <td>{p.driver_id}</td>
                      <td>{p.driver_name}</td>
                      <td className="dim">{p.team}</td>
                      <td className={`num ${p.predicted_position <= 3 ? "" : "dim"}`}>
                        {fw(p.win_probability! * 100, 5, 1)}
                      </td>
                      <td className="num">{fw(p.podium_probability! * 100, 5, 1)}</td>
                      <td className="num">{fw(p.points_probability! * 100, 5, 1)}</td>
                      <td className="num amber">{fw(p.expected_position, 4, 1)}</td>
                      <td className="num">{p.position_p10}</td>
                      <td className="num">{p.position_p90}</td>
                      <td>{hist && <Spark hist={hist} predicted={p.predicted_position} />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="twocol">
            <div>
              <div className="section-title">═══ SHAP <span>/ SELECTED DRIVER</span> ═══</div>
              <div className="picker">
                {predictions.map((p) => (
                  <button
                    key={p.driver_id}
                    className={selected === p.driver_id ? "on" : ""}
                    onClick={() => setSelected(p.driver_id)}
                  >
                    P{p.predicted_position.toString().padStart(2, "0")}·{p.driver_id}
                  </button>
                ))}
              </div>
              <div className="box">
                <h3>
                  {selectedRow.driver_id} — {selectedRow.driver_name}{" "}
                  <span className="tag">
                    [P{selectedRow.predicted_position} · WIN{" "}
                    {(selectedRow.win_probability! * 100).toFixed(1)}%]
                  </span>
                </h3>
                <div style={{ marginBottom: 10, color: "rgba(0,255,106,0.7)", fontSize: 11 }}>
                  Σ shap contributions (top 8) — green = lifts, red = hurts
                </div>
                {selectedShap.slice(0, 8).map((s) => {
                  const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
                  const pct = mag * 50;
                  return (
                    <div key={s.feature} className="shap-row">
                      <span className="dim">{s.feature}</span>
                      <div className="track">
                        {s.shap_value >= 0 ? (
                          <div className="fill-pos" style={{ width: `${pct}%` }} />
                        ) : (
                          <div className="fill-neg" style={{ width: `${pct}%` }} />
                        )}
                        <div className="mid" />
                      </div>
                      <span className={`num ${s.shap_value >= 0 ? "" : "red"}`}>
                        {s.shap_value >= 0 ? "+" : ""}
                        {s.shap_value.toFixed(3)}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="section-title" style={{ marginTop: 24 }}>
                ═══ GLOBAL FEATURE WEIGHT <span>/ XGB</span> ═══
              </div>
              <div className="box">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>FEATURE</th>
                      <th className="num">PCT</th>
                      <th>BAR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feature_importance.slice(0, 12).map((f, i) => (
                      <tr key={f.feature}>
                        <td className="dim">{(i + 1).toString().padStart(2, "0")}</td>
                        <td>{f.feature}</td>
                        <td className="num">{f.pct.toFixed(1)}%</td>
                        <td className="bar">{asciiBar(f.pct * 5, 14)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <div className="section-title">═══ SIDECAR <span>/ STATE</span> ═══</div>

              <div className="alert">
                <h3>! DNF WATCHLIST</h3>
                {dnfRisk.map((d) => (
                  <div key={d.id} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{d.id}</span>
                    <span>{d.pct.toFixed(1)}%</span>
                  </div>
                ))}
              </div>

              <div className="box" style={{ marginBottom: 14 }}>
                <h3>WEATHER · <span className="tag">FCAST</span></h3>
                <div className="kv">
                  <span className="k">Air</span><span className="v">24.3°C</span>
                  <span className="k">Track</span><span className="v">38.1°C</span>
                  <span className="k">Humidity</span><span className="v">58%</span>
                  <span className="k">Wind</span><span className="v">4.2 m/s</span>
                  <span className="k">Rain prob</span><span className="v">8%</span>
                  <span className="k">Wet flag</span><span className="v">0</span>
                </div>
              </div>

              <div className="box" style={{ marginBottom: 14 }}>
                <h3>CIRCUIT · <span className="tag">SAKHIR</span></h3>
                <div className="kv">
                  <span className="k">Length</span><span className="v">5.412 km</span>
                  <span className="k">Corners</span><span className="v">15</span>
                  <span className="k">DRS zones</span><span className="v">3</span>
                  <span className="k">Power sens.</span><span className="v">0.72</span>
                  <span className="k">SC prob</span><span className="v">35%</span>
                </div>
              </div>

              <div className="box">
                <h3>
                  RAW · <span className="tag">{selectedRow.driver_id}</span>
                </h3>
                <div className="kv" style={{ fontSize: 11 }}>
                  {Object.entries(selectedFeatures)
                    .slice(0, 18)
                    .map(([k, v]) => (
                      <div key={k} style={{ display: "contents" }}>
                        <span className="k">{k}</span>
                        <span className="v">
                          {typeof v === "number" ? v.toFixed(Math.abs(v) > 10 ? 1 : 3) : "—"}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>

          <div className="footer">
            <span>
              ██ SYS OK · LAG {clock % 4 === 0 ? "12" : "08"}ms · UP 4m11s
            </span>
            <span>DATA SRC: FASTF1 / JOLPICA / OPENWEATHERMAP / AZURE·GPT4O</span>
            <span className="amber">
              {cursorOn ? "▌" : " "}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
