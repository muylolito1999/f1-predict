import { useState } from "react";
import Switcher from "./Switcher";
import { DEMO, RACE_DRIVERS } from "./demoData";

/** Livery-ish color per team (2026 lineup). Used as solid bars. */
const TEAM_HEX: Record<string, string> = {
  "Red Bull Racing": "#1e2d5f",
  "McLaren": "#ff6400",
  "Ferrari": "#dc0000",
  "Mercedes": "#00a39a",
  "Williams": "#00a3ff",
  "Aston Martin": "#1a4d3a",
  "Alpine": "#0076b6",
  "Haas": "#4d4d4d",
  "Kick Sauber": "#52e252",
  "Racing Bulls": "#4a7ad2",
};

function teamHex(team: string): string {
  return TEAM_HEX[team] ?? "#1a1a1a";
}

function driverNumber(driverId: string): number {
  return RACE_DRIVERS.find((d) => d.id === driverId)?.number ?? 0;
}

function Roundel({ num, bg, fg }: { num: number; bg: string; fg: string }) {
  return (
    <div
      style={{
        width: 48,
        height: 48,
        borderRadius: "50%",
        background: bg,
        color: fg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Bebas Neue', sans-serif",
        fontSize: 24,
        letterSpacing: 1,
        border: "2px solid #1a1a1a",
        flexShrink: 0,
      }}
    >
      {num}
    </div>
  );
}

function BigBar({ pct, color, height = 8 }: { pct: number; color: string; height?: number }) {
  return (
    <div
      style={{
        background: "#e8ddbf",
        width: "100%",
        height,
        position: "relative",
        border: "1px solid #1a1a1a",
      }}
    >
      <div
        style={{
          background: color,
          width: `${Math.min(100, pct)}%`,
          height: "100%",
        }}
      />
    </div>
  );
}

function PositionDist({ hist, predicted, color }: { hist: number[]; predicted: number; color: string }) {
  const max = Math.max(...hist) || 1;
  const w = 160;
  const h = 36;
  const barW = w / hist.length;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <rect x={0} y={0} width={w} height={h} fill="#f4e8d0" stroke="#1a1a1a" strokeWidth={1} />
      {hist.map((c, i) => {
        const bh = (c / max) * (h - 4);
        const isPred = i + 1 === predicted;
        return (
          <rect
            key={i}
            x={i * barW + 1}
            y={h - bh - 1}
            width={Math.max(1, barW - 1.5)}
            height={bh}
            fill={isPred ? "#1a1a1a" : color}
            opacity={isPred ? 1 : 0.8}
          />
        );
      })}
    </svg>
  );
}

export default function Circuit() {
  const { predictions, metadata, feature_importance, shap_by_driver } = DEMO;
  const winner = predictions[0];
  const [selected, setSelected] = useState(winner.driver_id);
  const selectedRow = predictions.find((p) => p.driver_id === selected)!;
  const selectedShap = (shap_by_driver?.[selected] ?? []).slice(0, 6);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;0,9..40,900;1,9..40,400;1,9..40,700&display=swap');
        html, body { margin: 0; background: #f4e8d0; }
        .circ {
          min-height: 100vh;
          background: #f4e8d0;
          color: #1a1a1a;
          font-family: 'DM Sans', sans-serif;
          padding-bottom: 120px;
          overflow-x: hidden;
        }
        .liverystack {
          display: flex;
          height: 48px;
          overflow: hidden;
        }
        .liverystack > div { flex: 1; }

        .banner {
          padding: 60px 6vw 40px;
          position: relative;
        }
        .banner::before {
          content: '';
          position: absolute;
          inset: 0;
          background:
            radial-gradient(circle at 90% 10%, rgba(255,100,0,0.08), transparent 50%),
            radial-gradient(circle at 10% 90%, rgba(0,163,255,0.08), transparent 50%);
          pointer-events: none;
        }
        .banner-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 32px;
          font-weight: 700;
          letter-spacing: 2px;
          font-size: 12px;
          text-transform: uppercase;
          position: relative;
        }

        .hero-row {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 40px;
          align-items: end;
          position: relative;
        }
        .round-badge {
          background: #1a1a1a;
          color: #f4e8d0;
          width: 110px;
          height: 110px;
          border-radius: 50%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          font-family: 'Bebas Neue', sans-serif;
          line-height: 0.9;
          flex-shrink: 0;
        }
        .round-badge .label { font-size: 11px; letter-spacing: 3px; font-family: 'DM Sans', sans-serif; font-weight: 700; }
        .round-badge .num { font-size: 62px; color: #ff6400; }
        .hero-h1 {
          font-family: 'Bebas Neue', sans-serif;
          font-size: clamp(80px, 14vw, 200px);
          line-height: 0.82;
          letter-spacing: 2px;
          margin: 0;
          color: #1a1a1a;
        }
        .hero-h1 em {
          font-style: normal;
          color: #ff6400;
          -webkit-text-stroke: 0;
        }
        .hero-meta {
          font-family: 'DM Sans', sans-serif;
          font-size: 14px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 2px;
          text-align: right;
          line-height: 1.6;
        }
        .hero-meta span.accent { color: #ff6400; }

        .winner-callout {
          margin: 40px 0 0;
          display: grid;
          grid-template-columns: 1fr 300px;
          gap: 20px;
          align-items: stretch;
        }
        .callout-main {
          background: #1a1a1a;
          color: #f4e8d0;
          padding: 26px 30px;
          position: relative;
          overflow: hidden;
        }
        .callout-main::after {
          content: '';
          position: absolute;
          right: -40px; top: -40px;
          width: 180px; height: 180px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(255,100,0,0.4), transparent 70%);
        }
        .callout-main .tag {
          font-size: 11px;
          letter-spacing: 3px;
          color: #ff6400;
          font-weight: 700;
          text-transform: uppercase;
        }
        .callout-main .name {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 54px;
          letter-spacing: 1px;
          line-height: 1;
          margin: 6px 0;
        }
        .callout-main .bits {
          display: flex;
          gap: 28px;
          margin-top: 10px;
          font-size: 13px;
          font-weight: 500;
        }
        .callout-main .bits div span:first-child {
          display: block;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #a89e82;
          margin-bottom: 2px;
        }

        .section-band {
          background: #1a1a1a;
          color: #f4e8d0;
          padding: 14px 6vw;
          margin: 60px 0 32px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          position: relative;
        }
        .section-band::before,
        .section-band::after {
          content: '';
          position: absolute;
          top: 0; bottom: 0;
          width: 30px;
        }
        .section-band::before { left: 0; background: #ff6400; }
        .section-band::after { right: 0; background: #00a3ff; }
        .section-band .label {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 28px;
          letter-spacing: 4px;
          padding-left: 30px;
        }
        .section-band .meta {
          font-size: 11px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: #a89e82;
          padding-right: 30px;
        }

        .wrap { padding: 0 6vw; }

        .driver-row {
          display: grid;
          grid-template-columns: 44px 54px 2.5fr 1.5fr 1.5fr 1.5fr 180px;
          gap: 14px;
          align-items: center;
          padding: 10px 0;
          border-bottom: 1px solid rgba(26, 26, 26, 0.25);
          cursor: pointer;
          transition: background 150ms;
        }
        .driver-row:hover, .driver-row.on {
          background: rgba(26, 26, 26, 0.05);
        }
        .driver-row .pos {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 36px;
          letter-spacing: 1px;
          text-align: center;
          line-height: 1;
        }
        .driver-row.podium .pos { color: #ff6400; }
        .driver-row .team-swatch {
          width: 10px;
          height: 44px;
          flex-shrink: 0;
        }
        .driver-row .name {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 24px;
          letter-spacing: 1px;
          line-height: 1;
        }
        .driver-row .name small {
          display: block;
          font-family: 'DM Sans', sans-serif;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #555;
          font-weight: 700;
          margin-top: 4px;
        }
        .driver-row .stat {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 22px;
          line-height: 1;
        }
        .driver-row .stat small {
          display: block;
          font-family: 'DM Sans', sans-serif;
          font-size: 9px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #555;
          font-weight: 700;
          margin-top: 4px;
        }

        .header-row {
          display: grid;
          grid-template-columns: 44px 54px 2.5fr 1.5fr 1.5fr 1.5fr 180px;
          gap: 14px;
          padding: 8px 0;
          border-bottom: 3px solid #1a1a1a;
          font-size: 11px;
          letter-spacing: 2px;
          text-transform: uppercase;
          font-weight: 900;
        }

        .two-col {
          display: grid;
          grid-template-columns: 1.3fr 1fr;
          gap: 40px;
          margin-top: 20px;
        }
        @media (max-width: 960px) {
          .two-col, .winner-callout { grid-template-columns: 1fr; }
          .driver-row, .header-row { grid-template-columns: 40px 1fr 1fr; }
          .driver-row .team-swatch, .driver-row .stat:nth-child(n+4), .header-row > *:nth-child(n+4) { display: none; }
        }

        .box {
          border: 2px solid #1a1a1a;
          padding: 20px 24px;
        }
        .box h3 {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 32px;
          letter-spacing: 2px;
          margin: 0 0 14px;
          line-height: 1;
          border-bottom: 2px solid #1a1a1a;
          padding-bottom: 10px;
        }

        .imp-row {
          display: grid;
          grid-template-columns: 1fr 60px;
          gap: 12px;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px dashed rgba(26, 26, 26, 0.3);
        }
        .imp-row:last-child { border-bottom: 0; }
        .imp-row .name {
          font-size: 13px;
          font-weight: 500;
        }
        .imp-row .bar {
          height: 6px;
          background: #e8ddbf;
          border: 1px solid #1a1a1a;
          margin-top: 6px;
        }
        .imp-row .bar > div { height: 100%; background: #ff6400; }
        .imp-row .val {
          font-family: 'Bebas Neue', sans-serif;
          font-size: 22px;
          text-align: right;
        }

        .shap-row {
          display: grid;
          grid-template-columns: 1fr 80px;
          gap: 10px;
          padding: 8px 0;
          border-bottom: 1px dashed rgba(26, 26, 26, 0.3);
          font-size: 13px;
        }
        .shap-row .bar {
          position: relative;
          height: 14px;
          background: #e8ddbf;
          border: 1px solid #1a1a1a;
          margin-top: 6px;
        }
        .shap-row .mid { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 2px; background: #1a1a1a; }
        .shap-row .pos { position: absolute; left: 50%; top: 0; bottom: 0; background: #1a4d3a; }
        .shap-row .neg { position: absolute; right: 50%; top: 0; bottom: 0; background: #dc0000; }
        .shap-row .val { font-family: 'Bebas Neue', sans-serif; font-size: 22px; text-align: right; line-height: 1; }

        .picker-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 14px;
          margin-bottom: 20px;
        }
        .picker-chips button {
          background: transparent;
          border: 2px solid #1a1a1a;
          padding: 6px 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          cursor: pointer;
          color: #1a1a1a;
          text-transform: uppercase;
        }
        .picker-chips button.on {
          background: #1a1a1a;
          color: #f4e8d0;
        }

        .footer-stripes {
          display: flex;
          height: 16px;
          margin-top: 80px;
        }
      `}</style>

      <Switcher bg="#f4e8d0" fg="#1a1a1a" border="#1a1a1a" accent="#ff6400" />

      <div className="circ">
        {/* Top livery stripes */}
        <div className="liverystack">
          <div style={{ background: "#00a3ff" }} />
          <div style={{ background: "#ff6400" }} />
          <div style={{ background: "#dc0000" }} />
          <div style={{ background: "#1a4d3a" }} />
          <div style={{ background: "#1a1a1a" }} />
        </div>

        <div className="banner">
          <div className="banner-top">
            <span>Formula 1 · 2026 World Championship</span>
            <span>Grand Prix Programme</span>
          </div>
          <div className="hero-row">
            <div className="round-badge">
              <span className="label">Round</span>
              <span className="num">01</span>
            </div>
            <h1 className="hero-h1">
              Bahrain<br />
              <em>Grand Prix</em>
            </h1>
            <div className="hero-meta">
              Sakhir &nbsp;·&nbsp; 18 April MMXXVI<br />
              5.412 km &nbsp;·&nbsp; 57 laps<br />
              <span className="accent">Forecast issued pre-race</span>
            </div>
          </div>

          <div className="winner-callout">
            <div className="callout-main">
              <div className="tag">Predicted Winner · {(winner.win_probability! * 100).toFixed(1)}%</div>
              <div className="name">{winner.driver_name.toUpperCase()}</div>
              <div style={{ fontSize: 14, letterSpacing: 1, fontWeight: 500 }}>{winner.team}</div>
              <div className="bits">
                <div><span>Podium</span><span>{(winner.podium_probability! * 100).toFixed(0)}%</span></div>
                <div><span>Expected pos</span><span>P{winner.expected_position!.toFixed(1)}</span></div>
                <div><span>Range</span><span>P{winner.position_p10}–P{winner.position_p90}</span></div>
                <div><span>Confidence</span><span>{metadata.confidence}</span></div>
              </div>
            </div>
            <div className="callout-main" style={{ background: "#ff6400", color: "#1a1a1a" }}>
              <div className="tag" style={{ color: "#1a1a1a", opacity: 0.7 }}>Dark horse · P{predictions[4].predicted_position}</div>
              <div className="name" style={{ color: "#1a1a1a" }}>{predictions[4].driver_name.toUpperCase()}</div>
              <div style={{ fontSize: 12, fontWeight: 700 }}>
                Podium odds: {(predictions[4].podium_probability! * 100).toFixed(0)}% ·
                Win {(predictions[4].win_probability! * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        <div className="section-band">
          <span className="label">CLASSIFICATION</span>
          <span className="meta">Predicted order of finish · Monte Carlo verified</span>
        </div>

        <div className="wrap">
          <div className="header-row">
            <span>Pos</span>
            <span></span>
            <span>Driver</span>
            <span>Win</span>
            <span>Podium</span>
            <span>Points</span>
            <span>Distribution</span>
          </div>
          {predictions.map((p) => {
            const color = teamHex(p.team);
            const num = driverNumber(p.driver_id);
            const hist = DEMO.position_histograms[p.driver_id];
            return (
              <div
                key={p.driver_id}
                className={`driver-row ${selected === p.driver_id ? "on" : ""} ${p.predicted_position <= 3 ? "podium" : ""}`}
                onClick={() => setSelected(p.driver_id)}
              >
                <div className="pos">{p.predicted_position}</div>
                <Roundel num={num} bg={color} fg="#fff" />
                <div className="name">
                  {p.driver_name.toUpperCase()}
                  <small>{p.team}</small>
                </div>
                <div className="stat">
                  {(p.win_probability! * 100).toFixed(1)}%
                  <BigBar pct={p.win_probability! * 100 * 2.5} color="#ff6400" />
                </div>
                <div className="stat">
                  {(p.podium_probability! * 100).toFixed(0)}%
                  <BigBar pct={p.podium_probability! * 100} color="#00a3ff" />
                </div>
                <div className="stat">
                  {(p.points_probability! * 100).toFixed(0)}%
                  <BigBar pct={p.points_probability! * 100} color="#1a4d3a" />
                </div>
                <div>{hist && <PositionDist hist={hist} predicted={p.predicted_position} color={color} />}</div>
              </div>
            );
          })}
        </div>

        <div className="section-band">
          <span className="label">THE WHY</span>
          <span className="meta">Model diagnostics · Feature impact</span>
        </div>

        <div className="wrap">
          <div className="two-col">
            <div className="box">
              <h3>Global Feature Impact</h3>
              {feature_importance.slice(0, 10).map((f) => (
                <div key={f.feature} className="imp-row">
                  <div>
                    <div className="name">{f.feature}</div>
                    <div className="bar"><div style={{ width: `${Math.min(100, f.pct * 5)}%` }} /></div>
                  </div>
                  <div className="val">{f.pct.toFixed(1)}%</div>
                </div>
              ))}
            </div>

            <div className="box">
              <h3>{selectedRow.driver_name} · P{selectedRow.predicted_position}</h3>
              <div style={{ fontSize: 12, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, color: "#555", marginBottom: 10 }}>
                SHAP attribution — top contributors
              </div>
              {selectedShap.map((s) => {
                const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
                return (
                  <div key={s.feature} className="shap-row">
                    <div>
                      <div style={{ fontWeight: 500 }}>{s.feature}</div>
                      <div className="bar">
                        {s.shap_value >= 0 ? (
                          <div className="pos" style={{ width: `${mag * 50}%` }} />
                        ) : (
                          <div className="neg" style={{ width: `${mag * 50}%` }} />
                        )}
                        <div className="mid" />
                      </div>
                    </div>
                    <div className="val" style={{ color: s.shap_value >= 0 ? "#1a4d3a" : "#dc0000" }}>
                      {s.shap_value >= 0 ? "+" : ""}
                      {s.shap_value.toFixed(2)}
                    </div>
                  </div>
                );
              })}
              <div className="picker-chips">
                {predictions.map((p) => (
                  <button
                    key={p.driver_id}
                    className={selected === p.driver_id ? "on" : ""}
                    onClick={() => setSelected(p.driver_id)}
                  >
                    P{p.predicted_position} {p.driver_id}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="footer-stripes">
          <div style={{ background: "#1a1a1a", flex: 1 }} />
          <div style={{ background: "#ff6400", flex: 1 }} />
          <div style={{ background: "#00a3ff", flex: 1 }} />
          <div style={{ background: "#dc0000", flex: 1 }} />
          <div style={{ background: "#1a4d3a", flex: 1 }} />
        </div>
      </div>
    </>
  );
}
