import { useState } from "react";
import Switcher from "./Switcher";
import { DEMO } from "./demoData";

function Speedlines() {
  // Thin diagonal lines sliding across the hero
  return (
    <svg
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      preserveAspectRatio="none"
      viewBox="0 0 1000 400"
    >
      {Array.from({ length: 40 }).map((_, i) => {
        const y = (i * 400) / 40 + Math.sin(i) * 8;
        return (
          <line
            key={i}
            x1={-100}
            y1={y}
            x2={1200}
            y2={y - 60}
            stroke={i % 7 === 0 ? "#e10600" : "rgba(255,255,255,0.04)"}
            strokeWidth={i % 7 === 0 ? 1.5 : 1}
            style={{
              animation: `slip-streak 2.4s ${i * 0.08}s linear infinite`,
              opacity: i % 5 === 0 ? 0.4 : 0.18,
            }}
          />
        );
      })}
    </svg>
  );
}

function SpeedSpark({ hist, predicted }: { hist: number[]; predicted: number }) {
  const max = Math.max(...hist) || 1;
  const w = 120;
  const h = 22;
  const barW = w / hist.length;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <line x1={0} y1={h - 0.5} x2={w} y2={h - 0.5} stroke="rgba(255,255,255,0.15)" strokeWidth={1} />
      {hist.map((c, i) => {
        const bh = (c / max) * (h - 2);
        const isPred = i + 1 === predicted;
        return (
          <rect
            key={i}
            x={i * barW}
            y={h - bh - 1}
            width={barW - 0.5}
            height={bh}
            fill={isPred ? "#f4c430" : "#e10600"}
            opacity={isPred ? 1 : 0.85}
          />
        );
      })}
    </svg>
  );
}

export default function Slipstream() {
  const { predictions, metadata, feature_importance, shap_by_driver } = DEMO;
  const winner = predictions[0];
  const [selected, setSelected] = useState(winner.driver_id);
  const selectedRow = predictions.find((p) => p.driver_id === selected)!;
  const selectedShap = (shap_by_driver?.[selected] ?? []).slice(0, 6);

  // Build a marquee string from predictions
  const marquee = predictions
    .map((p) => `P${p.predicted_position.toString().padStart(2, "0")} ${p.driver_id} ${(p.win_probability! * 100).toFixed(1)}%`)
    .join("   //   ");

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Anton&family=Barlow+Semi+Condensed:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body { margin: 0; background: #0d0d0d; }
        .slip {
          min-height: 100vh;
          background: #0d0d0d;
          color: #fff;
          font-family: 'Barlow Semi Condensed', sans-serif;
          position: relative;
          overflow-x: hidden;
        }

        @keyframes slip-streak {
          0% { transform: translateX(-1200px); }
          100% { transform: translateX(1200px); }
        }
        @keyframes slip-in {
          0% { opacity: 0; transform: translateX(40px) skewX(-5deg); }
          100% { opacity: 1; transform: translateX(0) skewX(-5deg); }
        }
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }

        /* HERO */
        .hero {
          position: relative;
          height: 78vh;
          min-height: 520px;
          background:
            linear-gradient(105deg, #0d0d0d 0%, #0d0d0d 40%, #e10600 40%, #e10600 62%, #0d0d0d 62%, #0d0d0d 100%);
          overflow: hidden;
          clip-path: polygon(0 0, 100% 0, 100% 96%, 0 100%);
        }
        .hero-inner {
          position: relative;
          z-index: 2;
          padding: 80px 6vw 0;
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }
        .hero-top {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 12px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.8);
        }
        .hero-top .live {
          color: #f4c430;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .hero-top .live::before {
          content: '';
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #f4c430;
          animation: slip-pulse 1.2s ease-in-out infinite;
        }
        @keyframes slip-pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }

        .hero-title {
          font-family: 'Anton', sans-serif;
          font-size: clamp(110px, 19vw, 300px);
          line-height: 0.82;
          font-weight: 400;
          letter-spacing: -3px;
          text-transform: uppercase;
          margin: 0;
          transform: skewX(-4deg);
          display: inline-block;
          animation: slip-in 900ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
        }
        .hero-title .break {
          display: block;
          color: #fff;
          text-shadow: -4px 4px 0 rgba(0,0,0,0.2);
        }
        .hero-title .mark {
          display: inline-block;
          background: #0d0d0d;
          color: #f4c430;
          padding: 0 14px;
          transform: skewX(4deg);
        }

        .hero-bottom {
          position: relative;
          z-index: 2;
          padding-bottom: 40px;
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          gap: 40px;
          flex-wrap: wrap;
        }
        .hero-lede {
          font-family: 'Barlow Semi Condensed', sans-serif;
          font-size: 20px;
          line-height: 1.35;
          max-width: 460px;
          font-weight: 500;
        }
        .hero-lede b { color: #f4c430; font-weight: 700; }
        .hero-stats {
          display: flex;
          gap: 40px;
          font-family: 'Anton', sans-serif;
          text-transform: uppercase;
        }
        .hero-stats .hs {
          border-left: 3px solid #e10600;
          padding: 0 0 2px 12px;
          line-height: 0.9;
        }
        .hero-stats .hs .lbl {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 2px;
          color: rgba(255,255,255,0.6);
          display: block;
          margin-bottom: 8px;
          font-weight: 400;
        }
        .hero-stats .hs .val {
          font-size: 54px;
          letter-spacing: 1px;
        }

        /* MARQUEE */
        .marquee {
          overflow: hidden;
          background: #f4c430;
          color: #0d0d0d;
          font-family: 'Anton', sans-serif;
          font-size: 28px;
          letter-spacing: 3px;
          white-space: nowrap;
          padding: 10px 0;
          transform: skewY(-1deg);
          margin: -20px 0 0;
          position: relative;
          z-index: 10;
          border-top: 2px solid #0d0d0d;
          border-bottom: 2px solid #0d0d0d;
        }
        .marquee-track {
          display: inline-flex;
          animation: marquee 28s linear infinite;
        }
        .marquee-track span { padding-right: 40px; }

        /* MAIN CONTENT */
        .content {
          padding: 60px 6vw 120px;
          position: relative;
        }
        .section-head {
          display: flex;
          align-items: baseline;
          gap: 24px;
          margin: 40px 0 20px;
        }
        .section-head .num {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 14px;
          letter-spacing: 4px;
          color: #e10600;
        }
        .section-head h2 {
          font-family: 'Anton', sans-serif;
          font-size: clamp(48px, 7vw, 96px);
          line-height: 0.9;
          margin: 0;
          text-transform: uppercase;
          letter-spacing: 1px;
          font-weight: 400;
        }
        .section-head h2 em {
          font-style: italic;
          color: #e10600;
        }
        .section-sub {
          font-size: 16px;
          max-width: 640px;
          color: rgba(255, 255, 255, 0.65);
          margin-top: 10px;
        }

        /* GRID ROWS */
        .grid {
          margin-top: 40px;
        }
        .grid-head {
          display: grid;
          grid-template-columns: 90px 3fr 80px 100px 100px 100px 140px;
          gap: 20px;
          padding: 16px 20px;
          border-top: 3px solid #fff;
          border-bottom: 1px solid rgba(255,255,255,0.15);
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: rgba(255,255,255,0.6);
          font-weight: 500;
        }
        .row {
          display: grid;
          grid-template-columns: 90px 3fr 80px 100px 100px 100px 140px;
          gap: 20px;
          padding: 18px 20px;
          align-items: center;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          cursor: pointer;
          transition: background 180ms, transform 180ms;
          position: relative;
        }
        .row::before {
          content: '';
          position: absolute;
          left: 0; top: 0; bottom: 0;
          width: 0;
          background: #e10600;
          transition: width 180ms;
        }
        .row:hover, .row.on {
          background: rgba(225, 6, 0, 0.06);
          transform: translateX(6px);
        }
        .row:hover::before, .row.on::before {
          width: 6px;
        }
        .row.top3 .pos {
          color: #f4c430;
        }
        .pos {
          font-family: 'Anton', sans-serif;
          font-size: 52px;
          line-height: 0.9;
          letter-spacing: -1px;
          color: #fff;
        }
        .pos em {
          font-size: 22px;
          color: rgba(255,255,255,0.5);
          font-style: normal;
          margin-left: -2px;
        }
        .dr-name {
          font-family: 'Anton', sans-serif;
          font-size: 32px;
          line-height: 1;
          letter-spacing: 1px;
          text-transform: uppercase;
          transform: skewX(-3deg);
          display: inline-block;
        }
        .dr-team {
          display: block;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 2px;
          color: rgba(255,255,255,0.5);
          text-transform: uppercase;
          margin-top: 4px;
        }
        .stat-big {
          font-family: 'Anton', sans-serif;
          font-size: 32px;
          line-height: 1;
          letter-spacing: 0.5px;
        }
        .stat-big.accent { color: #e10600; }
        .stat-big small {
          display: block;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 9px;
          letter-spacing: 2px;
          color: rgba(255,255,255,0.45);
          margin-top: 4px;
          font-weight: 500;
          font-style: normal;
        }
        .chip {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 8px;
          background: #1a1a1a;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 1px;
          color: #f4c430;
        }

        /* ANALYSIS */
        .analysis {
          display: grid;
          grid-template-columns: 1.3fr 1fr;
          gap: 60px;
          margin-top: 80px;
        }
        @media (max-width: 960px) { .analysis { grid-template-columns: 1fr; } }

        .imp-col {
          border-top: 3px solid #e10600;
          padding-top: 30px;
        }
        .imp-col .heading {
          font-family: 'Anton', sans-serif;
          font-size: 48px;
          letter-spacing: 1px;
          line-height: 0.95;
          text-transform: uppercase;
          margin: 0 0 14px;
        }
        .imp-col .heading em { color: #e10600; font-style: italic; }

        .imp-row {
          display: grid;
          grid-template-columns: 1fr 80px;
          gap: 14px;
          padding: 10px 0;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          align-items: center;
        }
        .imp-row .fname {
          font-family: 'Barlow Semi Condensed', sans-serif;
          font-size: 15px;
          font-weight: 500;
        }
        .imp-row .fbar {
          height: 4px;
          background: rgba(255,255,255,0.08);
          margin-top: 6px;
          position: relative;
        }
        .imp-row .fbar > span {
          position: absolute; left: 0; top: 0; bottom: 0;
          background: linear-gradient(90deg, #e10600, #f4c430);
        }
        .imp-row .fval {
          font-family: 'Anton', sans-serif;
          font-size: 30px;
          letter-spacing: 0.5px;
          text-align: right;
          line-height: 1;
        }

        .picker {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin: 20px 0 28px;
        }
        .picker button {
          background: #1a1a1a;
          color: #fff;
          border: 1px solid #333;
          padding: 8px 12px;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 1px;
          cursor: pointer;
          font-weight: 500;
          transition: all 150ms;
        }
        .picker button:hover { border-color: #e10600; }
        .picker button.on {
          background: #e10600;
          color: #fff;
          border-color: #e10600;
        }

        .shap-card {
          background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
          padding: 28px;
          border-left: 4px solid #e10600;
        }
        .shap-card h4 {
          font-family: 'Anton', sans-serif;
          font-size: 38px;
          margin: 0 0 6px;
          line-height: 1;
          letter-spacing: 1px;
          text-transform: uppercase;
        }
        .shap-card .deck {
          font-size: 14px;
          color: rgba(255,255,255,0.6);
          margin: 0 0 24px;
        }
        .shap-row {
          display: grid;
          grid-template-columns: 160px 1fr 70px;
          gap: 12px;
          padding: 10px 0;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          align-items: center;
          font-size: 13px;
        }
        .shap-row .sfeat {
          font-family: 'Barlow Semi Condensed', sans-serif;
          font-weight: 500;
        }
        .shap-row .track {
          height: 12px;
          background: rgba(255,255,255,0.06);
          position: relative;
        }
        .shap-row .mid { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 2px; background: rgba(255,255,255,0.4); }
        .shap-row .pos { position: absolute; left: 50%; top: 0; bottom: 0; background: #f4c430; }
        .shap-row .neg { position: absolute; right: 50%; top: 0; bottom: 0; background: #e10600; }
        .shap-row .sval {
          font-family: 'Anton', sans-serif;
          font-size: 26px;
          line-height: 1;
          text-align: right;
          letter-spacing: 0.5px;
        }

        .cut {
          height: 16px;
          background: repeating-linear-gradient(135deg, #e10600, #e10600 20px, #0d0d0d 20px, #0d0d0d 40px);
          margin: 100px 0 40px;
          transform: skewY(-1deg);
        }

        .footer {
          display: flex;
          justify-content: space-between;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: rgba(255,255,255,0.45);
          flex-wrap: wrap;
          gap: 12px;
        }
      `}</style>

      <Switcher bg="#0d0d0d" fg="#fff" border="#333" accent="#e10600" />

      <div className="slip">
        <div className="hero">
          <Speedlines />
          <div className="hero-inner">
            <div className="hero-top">
              <span>F1 Predict · Model v0.3 · Ensemble + MC + SHAP</span>
              <span className="live">LIVE FORECAST · PRE-RACE</span>
              <span>{metadata.year} · R{metadata.round?.toString().padStart(2, "0")} · SAKHIR</span>
            </div>

            <div>
              <h1 className="hero-title">
                <span className="break">SECTOR</span>
                <span className="mark">ONE</span>
              </h1>
            </div>

            <div className="hero-bottom">
              <p className="hero-lede">
                The ensemble has filed its pre-race verdict.
                <b> 20 drivers. 5,000 simulations. One grid of truth.</b>
              </p>
              <div className="hero-stats">
                <div className="hs">
                  <span className="lbl">Confidence</span>
                  <span className="val">{metadata.confidence}</span>
                </div>
                <div className="hs">
                  <span className="lbl">P1 lock</span>
                  <span className="val">{(winner.win_probability! * 100).toFixed(1)}%</span>
                </div>
                <div className="hs">
                  <span className="lbl">σ noise</span>
                  <span className="val">0.25</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="marquee">
          <div className="marquee-track">
            <span>{marquee}</span>
            <span>{marquee}</span>
          </div>
        </div>

        <div className="content">
          <div className="section-head">
            <span className="num">01 //</span>
            <h2>
              The <em>grid</em>
            </h2>
          </div>
          <p className="section-sub">
            Sorted by expected finish position. Every row is one driver, one
            set of probabilities, one Monte Carlo distribution of where they
            actually end up when the race is re-run 5,000 times over.
          </p>

          <div className="grid">
            <div className="grid-head">
              <span>Pos</span>
              <span>Driver</span>
              <span>Expected</span>
              <span>Win</span>
              <span>Podium</span>
              <span>Points</span>
              <span>Distribution</span>
            </div>
            {predictions.map((p) => {
              const hist = DEMO.position_histograms[p.driver_id];
              return (
                <div
                  key={p.driver_id}
                  className={`row ${p.predicted_position <= 3 ? "top3" : ""} ${selected === p.driver_id ? "on" : ""}`}
                  onClick={() => setSelected(p.driver_id)}
                >
                  <div className="pos">
                    {p.predicted_position.toString().padStart(2, "0")}
                  </div>
                  <div>
                    <span className="dr-name">{p.driver_name}</span>
                    <span className="dr-team">{p.team}</span>
                  </div>
                  <div className="stat-big">
                    P{p.expected_position!.toFixed(1)}
                    <small>mean MC</small>
                  </div>
                  <div className={`stat-big ${p.predicted_position <= 3 ? "accent" : ""}`}>
                    {(p.win_probability! * 100).toFixed(1)}
                    <small>win %</small>
                  </div>
                  <div className="stat-big">
                    {(p.podium_probability! * 100).toFixed(0)}
                    <small>podium %</small>
                  </div>
                  <div className="stat-big">
                    {(p.points_probability! * 100).toFixed(0)}
                    <small>points %</small>
                  </div>
                  <div>
                    {hist && <SpeedSpark hist={hist} predicted={p.predicted_position} />}
                    <small style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, letterSpacing: 1, color: "rgba(255,255,255,0.45)" }}>
                      P{p.position_p10}–P{p.position_p90}
                    </small>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="analysis">
            <div className="imp-col">
              <div className="section-head" style={{ margin: 0 }}>
                <span className="num">02 //</span>
              </div>
              <h3 className="heading">
                What the <em>model</em> cared about
              </h3>
              <p className="section-sub" style={{ marginBottom: 24 }}>
                Global feature importance, pulled from the XGBoost head.
                Long-run pace dominates — as ever at Bahrain.
              </p>
              {feature_importance.slice(0, 10).map((f) => (
                <div key={f.feature} className="imp-row">
                  <div>
                    <div className="fname">{f.feature}</div>
                    <div className="fbar">
                      <span style={{ width: `${Math.min(100, f.pct * 5)}%` }} />
                    </div>
                  </div>
                  <div className="fval">{f.pct.toFixed(1)}</div>
                </div>
              ))}
            </div>

            <div>
              <div className="section-head" style={{ margin: 0 }}>
                <span className="num">03 //</span>
              </div>
              <h3 className="heading">
                Why <em>{selectedRow.driver_id}</em>?
              </h3>
              <div className="picker">
                {predictions.map((p) => (
                  <button
                    key={p.driver_id}
                    className={selected === p.driver_id ? "on" : ""}
                    onClick={() => setSelected(p.driver_id)}
                  >
                    P{p.predicted_position.toString().padStart(2, "0")} · {p.driver_id}
                  </button>
                ))}
              </div>

              <div className="shap-card">
                <h4>{selectedRow.driver_name}</h4>
                <p className="deck">
                  P{selectedRow.predicted_position} · Win{" "}
                  {(selectedRow.win_probability! * 100).toFixed(1)}% · Expected P
                  {selectedRow.expected_position!.toFixed(1)} ·{" "}
                  <span className="chip">SHAP · top 6</span>
                </p>

                {selectedShap.map((s) => {
                  const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
                  return (
                    <div key={s.feature} className="shap-row">
                      <span className="sfeat">{s.feature}</span>
                      <div className="track">
                        {s.shap_value >= 0 ? (
                          <div className="pos" style={{ width: `${mag * 50}%` }} />
                        ) : (
                          <div className="neg" style={{ width: `${mag * 50}%` }} />
                        )}
                        <div className="mid" />
                      </div>
                      <span className="sval" style={{ color: s.shap_value >= 0 ? "#f4c430" : "#e10600" }}>
                        {s.shap_value >= 0 ? "+" : ""}
                        {s.shap_value.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="cut" />

          <div className="footer">
            <span>F1 PREDICT // 2026 // BAHRAIN // ROUND 01</span>
            <span>{metadata.sessions_used}</span>
            <span>SET IN ANTON / BARLOW / IBM PLEX MONO</span>
          </div>
        </div>
      </div>
    </>
  );
}
