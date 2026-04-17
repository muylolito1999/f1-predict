import { useState } from "react";
import Switcher from "./Switcher";
import { DEMO } from "./demoData";

const ROMAN = [
  "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
  "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
];

function RadialProb({ pct, size = 120, color = "#d4af37" }: { pct: number; size?: number; color?: string }) {
  const r = size / 2 - 8;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct / 100);
  return (
    <svg width={size} height={size}>
      <circle
        cx={c}
        cy={c}
        r={r}
        fill="none"
        stroke="rgba(212, 175, 55, 0.15)"
        strokeWidth={2}
      />
      <circle
        cx={c}
        cy={c}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${c} ${c})`}
        style={{ transition: "stroke-dashoffset 600ms ease" }}
      />
      <text
        x={c}
        y={c - 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#f5f0e8"
        fontFamily="'Instrument Serif', serif"
        fontSize={size * 0.28}
        fontStyle="italic"
      >
        {pct.toFixed(1)}
      </text>
      <text
        x={c}
        y={c + size * 0.18}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={color}
        fontFamily="'Cormorant Garamond', serif"
        fontSize={10}
        letterSpacing={3}
      >
        PERCENT
      </text>
    </svg>
  );
}

function HairlineDist({ hist, predicted }: { hist: number[]; predicted: number }) {
  const max = Math.max(...hist) || 1;
  const w = 140;
  const h = 24;
  const gap = 0;
  const barW = w / hist.length;
  return (
    <svg width={w} height={h}>
      <line x1={0} y1={h - 1} x2={w} y2={h - 1} stroke="rgba(212, 175, 55, 0.3)" strokeWidth={0.5} />
      {hist.map((c, i) => {
        const bh = (c / max) * (h - 3);
        const isPred = i + 1 === predicted;
        return (
          <rect
            key={i}
            x={i * barW + gap}
            y={h - bh - 1}
            width={Math.max(1, barW - gap * 2)}
            height={bh}
            fill={isPred ? "#d4af37" : "#f5f0e8"}
            opacity={isPred ? 1 : 0.4}
          />
        );
      })}
    </svg>
  );
}

export default function Nocturne() {
  const { predictions, metadata, feature_importance, shap_by_driver } = DEMO;
  const winner = predictions[0];
  const [selected, setSelected] = useState(winner.driver_id);
  const selectedRow = predictions.find((p) => p.driver_id === selected)!;
  const selectedShap = (shap_by_driver?.[selected] ?? []).slice(0, 5);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body { margin: 0; background: #04080f; }
        .noct {
          min-height: 100vh;
          background:
            radial-gradient(ellipse at 20% 0%, rgba(212, 175, 55, 0.08), transparent 50%),
            radial-gradient(ellipse at 100% 80%, rgba(212, 175, 55, 0.04), transparent 60%),
            linear-gradient(180deg, #0a1628 0%, #04080f 80%);
          color: #f5f0e8;
          font-family: 'Cormorant Garamond', Georgia, serif;
          font-weight: 300;
          padding: 72px 6vw 140px;
          position: relative;
          overflow-x: hidden;
        }
        .noct::before {
          content: '';
          position: fixed;
          inset: 0;
          background-image:
            radial-gradient(1px 1px at 20% 30%, rgba(245, 240, 232, 0.4), transparent),
            radial-gradient(1px 1px at 40% 70%, rgba(245, 240, 232, 0.3), transparent),
            radial-gradient(1px 1px at 70% 20%, rgba(245, 240, 232, 0.35), transparent),
            radial-gradient(1px 1px at 90% 60%, rgba(245, 240, 232, 0.25), transparent),
            radial-gradient(1px 1px at 15% 85%, rgba(245, 240, 232, 0.2), transparent);
          pointer-events: none;
          opacity: 0.5;
        }

        .nav {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 4px;
          text-transform: uppercase;
          color: #d4af37;
          margin-bottom: 80px;
        }
        .nav .hair {
          flex: 1;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(212,175,55,0.6), transparent);
          margin: 0 32px;
        }

        .hero {
          text-align: center;
          padding: 40px 0 90px;
          position: relative;
        }
        .hero .meta {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 6px;
          text-transform: uppercase;
          color: #d4af37;
          margin-bottom: 30px;
        }
        .hero h1 {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(80px, 13vw, 200px);
          font-weight: 400;
          line-height: 0.9;
          letter-spacing: -4px;
          margin: 0;
          color: #f5f0e8;
        }
        .hero h1 em {
          font-style: italic;
          color: #d4af37;
          display: block;
          font-size: 0.75em;
        }
        .hero .sub {
          font-family: 'Cormorant Garamond', serif;
          font-size: 22px;
          font-style: italic;
          color: rgba(245, 240, 232, 0.7);
          margin: 40px auto 0;
          max-width: 600px;
          font-weight: 300;
        }
        .hero .rule {
          width: 80px;
          height: 1px;
          background: #d4af37;
          margin: 40px auto 0;
        }

        .section-head {
          text-align: center;
          margin: 80px 0 50px;
        }
        .section-head .tag {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 6px;
          text-transform: uppercase;
          color: #d4af37;
          display: block;
          margin-bottom: 20px;
        }
        .section-head .title {
          font-family: 'Instrument Serif', serif;
          font-size: 56px;
          font-weight: 400;
          line-height: 1;
          margin: 0;
        }
        .section-head .title em {
          font-style: italic;
          color: #d4af37;
        }

        .winner-stage {
          display: grid;
          grid-template-columns: 1.5fr 1fr;
          gap: 80px;
          align-items: center;
          max-width: 1100px;
          margin: 0 auto;
          padding: 50px 0;
          border-top: 1px solid rgba(212, 175, 55, 0.3);
          border-bottom: 1px solid rgba(212, 175, 55, 0.3);
          position: relative;
        }
        @media (max-width: 900px) { .winner-stage { grid-template-columns: 1fr; } }
        .winner-stage::before {
          content: 'I';
          position: absolute;
          top: -30px;
          left: 40px;
          background: #04080f;
          padding: 0 16px;
          color: #d4af37;
          font-family: 'Instrument Serif', serif;
          font-style: italic;
          font-size: 32px;
        }
        .winner-label {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 5px;
          text-transform: uppercase;
          color: #d4af37;
          margin-bottom: 14px;
        }
        .winner-name {
          font-family: 'Instrument Serif', serif;
          font-size: 80px;
          line-height: 0.9;
          font-weight: 400;
          color: #f5f0e8;
          margin: 0;
          letter-spacing: -2px;
        }
        .winner-name em {
          font-style: italic;
          display: block;
          color: #d4af37;
          font-size: 36px;
          margin-top: 8px;
          letter-spacing: 0;
        }
        .winner-stats {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px 40px;
          margin-top: 40px;
          font-family: 'Cormorant Garamond', serif;
          font-weight: 400;
        }
        .winner-stats .k {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 9px;
          letter-spacing: 4px;
          text-transform: uppercase;
          color: #a89a6f;
        }
        .winner-stats .v {
          font-family: 'Instrument Serif', serif;
          font-style: italic;
          font-size: 32px;
          color: #f5f0e8;
          margin-top: 2px;
        }
        .winner-visual { display: flex; justify-content: center; align-items: center; }

        /* Classification table — very thin rules, generous padding */
        .classification {
          max-width: 1000px;
          margin: 0 auto;
        }
        .cl-row {
          display: grid;
          grid-template-columns: 50px 50px 1fr 70px 70px 80px 70px 150px;
          gap: 18px;
          padding: 22px 10px;
          align-items: center;
          border-bottom: 1px solid rgba(212, 175, 55, 0.15);
          cursor: pointer;
          transition: background 150ms ease, padding 200ms ease;
        }
        .cl-row:hover {
          background: rgba(212, 175, 55, 0.04);
        }
        .cl-row.on {
          background: rgba(212, 175, 55, 0.08);
        }
        .cl-header {
          display: grid;
          grid-template-columns: 50px 50px 1fr 70px 70px 80px 70px 150px;
          gap: 18px;
          padding: 10px;
          border-bottom: 2px solid rgba(212, 175, 55, 0.5);
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: #a89a6f;
        }
        .cl-row .rank {
          font-family: 'Instrument Serif', serif;
          font-style: italic;
          color: #d4af37;
          font-size: 24px;
          text-align: right;
        }
        .cl-row .num {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 16px;
          color: #a89a6f;
          font-weight: 500;
        }
        .cl-row .name {
          font-family: 'Instrument Serif', serif;
          font-size: 28px;
          line-height: 1.1;
          color: #f5f0e8;
        }
        .cl-row .name small {
          display: block;
          font-family: 'Cormorant Garamond', serif;
          font-size: 14px;
          font-style: italic;
          color: #a89a6f;
          margin-top: 2px;
        }
        .cl-row .stat {
          font-family: 'Instrument Serif', serif;
          font-size: 22px;
          text-align: right;
          font-variant-numeric: tabular-nums;
        }
        .cl-row .stat.gold { color: #d4af37; }

        .diagnostics {
          max-width: 1100px;
          margin: 60px auto 0;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 60px;
        }
        @media (max-width: 900px) { .diagnostics { grid-template-columns: 1fr; } }

        .diag-box {
          border-top: 1px solid rgba(212, 175, 55, 0.3);
          padding-top: 30px;
        }
        .diag-box h3 {
          font-family: 'Instrument Serif', serif;
          font-weight: 400;
          font-size: 32px;
          margin: 0 0 8px;
          color: #f5f0e8;
        }
        .diag-box h3 em { font-style: italic; color: #d4af37; }
        .diag-box .note {
          font-family: 'Cormorant Garamond', serif;
          font-style: italic;
          font-size: 15px;
          color: rgba(245, 240, 232, 0.6);
          margin: 0 0 22px;
        }

        .imp-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }
        .imp-list li {
          display: grid;
          grid-template-columns: 1fr 60px;
          gap: 14px;
          padding: 14px 0;
          align-items: center;
          border-bottom: 1px solid rgba(212, 175, 55, 0.1);
        }
        .imp-list .imp-name {
          font-family: 'Cormorant Garamond', serif;
          font-size: 17px;
          font-style: italic;
        }
        .imp-list .imp-bar {
          height: 1px;
          background: rgba(212, 175, 55, 0.15);
          margin-top: 6px;
          position: relative;
        }
        .imp-list .imp-bar > span {
          position: absolute;
          left: 0; top: -1px; bottom: -1px;
          background: #d4af37;
        }
        .imp-list .imp-val {
          font-family: 'Instrument Serif', serif;
          font-style: italic;
          font-size: 20px;
          text-align: right;
          color: #d4af37;
        }

        .shap-row {
          display: grid;
          grid-template-columns: 180px 1fr 70px;
          gap: 14px;
          padding: 12px 0;
          align-items: center;
          border-bottom: 1px solid rgba(212, 175, 55, 0.1);
        }
        .shap-row .sname {
          font-family: 'Cormorant Garamond', serif;
          font-size: 15px;
          font-style: italic;
          color: rgba(245, 240, 232, 0.85);
        }
        .shap-row .track {
          height: 2px;
          background: rgba(212, 175, 55, 0.2);
          position: relative;
        }
        .shap-row .mid { position: absolute; left: 50%; top: -4px; bottom: -4px; width: 1px; background: rgba(212, 175, 55, 0.5); }
        .shap-row .pos { position: absolute; left: 50%; top: -1px; bottom: -1px; background: #d4af37; }
        .shap-row .neg { position: absolute; right: 50%; top: -1px; bottom: -1px; background: #8b3a47; }
        .shap-row .sval {
          font-family: 'Instrument Serif', serif;
          font-style: italic;
          font-size: 20px;
          text-align: right;
        }

        .picker {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 20px;
        }
        .picker button {
          background: transparent;
          border: 1px solid rgba(212, 175, 55, 0.3);
          padding: 6px 10px;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 2px;
          cursor: pointer;
          color: #a89a6f;
        }
        .picker button.on {
          background: #d4af37;
          color: #0a1628;
          border-color: #d4af37;
        }

        .colophon {
          max-width: 1000px;
          margin: 120px auto 0;
          padding-top: 40px;
          border-top: 1px solid rgba(212, 175, 55, 0.3);
          text-align: center;
          font-family: 'Cormorant Garamond', serif;
          font-style: italic;
          font-size: 14px;
          color: rgba(245, 240, 232, 0.5);
        }
      `}</style>

      <Switcher bg="#0a1628" fg="#f5f0e8" border="rgba(212,175,55,0.3)" accent="#d4af37" />

      <div className="noct">
        <div className="nav">
          <span>Nocturne · An F1 Brief</span>
          <div className="hair" />
          <span>{metadata.year} · Round {metadata.round}</span>
        </div>

        <section className="hero">
          <div className="meta">Predictions · Issued Pre-Race · 18 iv mmxxvi</div>
          <h1>
            Bahrain
            <em>Grand Prix</em>
          </h1>
          <p className="sub">
            A precise forecast, composed after the lights of free practice
            had gone out. Five thousand simulations — discreetly run.
          </p>
          <div className="rule" />
        </section>

        <div className="section-head">
          <span className="tag">Overture</span>
          <h2 className="title">
            The <em>favourite</em>
          </h2>
        </div>

        <section className="winner-stage">
          <div>
            <div className="winner-label">By the ensemble's measure</div>
            <h3 className="winner-name">
              Max <em>Verstappen</em>
            </h3>
            <div className="winner-stats">
              <div>
                <div className="k">Team</div>
                <div className="v">{winner.team}</div>
              </div>
              <div>
                <div className="k">Podium</div>
                <div className="v">{(winner.podium_probability! * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div className="k">Expected</div>
                <div className="v">P{winner.expected_position!.toFixed(1)}</div>
              </div>
              <div>
                <div className="k">Range</div>
                <div className="v">P{winner.position_p10}–P{winner.position_p90}</div>
              </div>
            </div>
          </div>
          <div className="winner-visual">
            <RadialProb pct={winner.win_probability! * 100} size={220} />
          </div>
        </section>

        <div className="section-head">
          <span className="tag">Movement II</span>
          <h2 className="title">
            The <em>full</em> grid
          </h2>
        </div>

        <div className="classification">
          <div className="cl-header">
            <span></span>
            <span>№</span>
            <span>Driver</span>
            <span style={{ textAlign: "right" }}>Win</span>
            <span style={{ textAlign: "right" }}>Podium</span>
            <span style={{ textAlign: "right" }}>Expected</span>
            <span style={{ textAlign: "right" }}>Range</span>
            <span style={{ textAlign: "center" }}>Distribution</span>
          </div>
          {predictions.map((p, i) => {
            const num = i + 1;
            const hist = DEMO.position_histograms[p.driver_id];
            return (
              <div
                key={p.driver_id}
                className={`cl-row ${selected === p.driver_id ? "on" : ""}`}
                onClick={() => setSelected(p.driver_id)}
              >
                <span className="rank">{ROMAN[i]}</span>
                <span className="num">{num.toString().padStart(2, "0")}</span>
                <div>
                  <div className="name">
                    {p.driver_name}
                    <small>{p.team}</small>
                  </div>
                </div>
                <span className={`stat ${i < 3 ? "gold" : ""}`}>
                  {(p.win_probability! * 100).toFixed(1)}
                </span>
                <span className="stat">
                  {(p.podium_probability! * 100).toFixed(0)}
                </span>
                <span className="stat">
                  P{p.expected_position!.toFixed(1)}
                </span>
                <span className="stat" style={{ fontSize: 15, fontStyle: "italic", color: "#a89a6f" }}>
                  {p.position_p10}–{p.position_p90}
                </span>
                <span style={{ textAlign: "center" }}>
                  {hist && <HairlineDist hist={hist} predicted={p.predicted_position} />}
                </span>
              </div>
            );
          })}
        </div>

        <div className="section-head">
          <span className="tag">Movement III</span>
          <h2 className="title">
            The <em>reasons</em>
          </h2>
        </div>

        <div className="diagnostics">
          <div className="diag-box">
            <h3>
              Global <em>weight</em>
            </h3>
            <p className="note">
              What the model paid attention to, aggregated over every driver.
            </p>
            <ol className="imp-list">
              {feature_importance.slice(0, 10).map((f) => (
                <li key={f.feature}>
                  <div>
                    <div className="imp-name">{f.feature}</div>
                    <div className="imp-bar">
                      <span style={{ width: `${Math.min(100, f.pct * 5)}%` }} />
                    </div>
                  </div>
                  <span className="imp-val">{f.pct.toFixed(1)}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="diag-box">
            <h3>
              On <em>{selectedRow.driver_name}</em>
            </h3>
            <p className="note">
              The features that made this driver's ranking the way it is.
            </p>
            <div className="picker">
              {predictions.slice(0, 12).map((p) => (
                <button
                  key={p.driver_id}
                  className={selected === p.driver_id ? "on" : ""}
                  onClick={() => setSelected(p.driver_id)}
                >
                  {p.driver_id}
                </button>
              ))}
            </div>
            {selectedShap.map((s) => {
              const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
              return (
                <div key={s.feature} className="shap-row">
                  <span className="sname">{s.feature}</span>
                  <div className="track">
                    {s.shap_value >= 0 ? (
                      <span className="pos" style={{ width: `${mag * 50}%` }} />
                    ) : (
                      <span className="neg" style={{ width: `${mag * 50}%` }} />
                    )}
                    <span className="mid" />
                  </div>
                  <span className="sval" style={{ color: s.shap_value >= 0 ? "#d4af37" : "#c56b79" }}>
                    {s.shap_value >= 0 ? "+" : ""}
                    {s.shap_value.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="colophon">
          Composed on the terrace · Set in Instrument Serif &amp; Cormorant Garamond<br />
          Model confidence — <span style={{ color: "#d4af37" }}>{metadata.confidence}</span>
        </div>
      </div>
    </>
  );
}
