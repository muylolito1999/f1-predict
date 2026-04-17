import { useState } from "react";
import Switcher from "./Switcher";
import { DEMO } from "./demoData";

/** Roman numerals for rank column. */
const ROMAN = [
  "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
  "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx",
];

function NoiseOverlay() {
  return (
    <svg
      width="0"
      height="0"
      style={{ position: "absolute" }}
      aria-hidden
    >
      <filter id="paper-noise">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" />
        <feColorMatrix values="0 0 0 0 0.05  0 0 0 0 0.04  0 0 0 0 0.02  0 0 0 0.08 0" />
      </filter>
    </svg>
  );
}

/** Thin SVG position-distribution drawn like a Tufte small-multiple. */
function MiniDist({ hist, predicted }: { hist: number[]; predicted: number }) {
  const max = Math.max(...hist);
  const width = 120;
  const height = 18;
  const barW = width / hist.length;
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {hist.map((c, i) => {
        const h = (c / max) * (height - 2);
        return (
          <rect
            key={i}
            x={i * barW}
            y={height - h}
            width={barW - 0.4}
            height={h}
            fill="#0a0a0a"
            opacity={0.75}
          />
        );
      })}
      <line
        x1={(predicted - 0.5) * barW}
        x2={(predicted - 0.5) * barW}
        y1={0}
        y2={height}
        stroke="#c41e3a"
        strokeWidth={1.2}
      />
    </svg>
  );
}

export default function Paddock() {
  const { predictions, metadata, feature_importance, shap_by_driver } = DEMO;
  const winner = predictions[0];
  const [selected, setSelected] = useState(winner.driver_id);
  const selectedShap = (shap_by_driver?.[selected] ?? []).slice(0, 5);
  const topFeatures = feature_importance.slice(0, 8);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,700;0,9..144,900;1,9..144,400;1,9..144,700&family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body {
          margin: 0;
          background: #efeadf;
        }
        .paddock {
          min-height: 100vh;
          background:
            radial-gradient(ellipse at top, rgba(196,30,58,0.04), transparent 60%),
            #f4f1ea;
          color: #121010;
          font-family: 'EB Garamond', Georgia, serif;
          font-size: 17px;
          line-height: 1.55;
          padding: 60px 6vw 140px;
          position: relative;
          overflow-x: hidden;
        }
        .paddock::before {
          content: '';
          position: absolute;
          inset: 0;
          background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence baseFrequency='0.85' numOctaves='2'/><feColorMatrix values='0 0 0 0 0.06  0 0 0 0 0.05  0 0 0 0 0.03  0 0 0 0.08 0'/></filter><rect width='200' height='200' filter='url(%23n)'/></svg>");
          pointer-events: none;
          opacity: 0.35;
          mix-blend-mode: multiply;
        }
        .paddock > * { position: relative; z-index: 1; }

        .masthead {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          border-top: 3px solid #121010;
          border-bottom: 1px solid #121010;
          padding: 14px 0;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 3px;
          text-transform: uppercase;
        }
        .masthead .red { color: #c41e3a; font-weight: 500; }

        .hero {
          margin: 60px 0 40px;
          display: grid;
          grid-template-columns: 1fr 380px;
          gap: 60px;
          align-items: end;
        }
        @media (max-width: 960px) { .hero { grid-template-columns: 1fr; } }

        .folio {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 12px;
          letter-spacing: 5px;
          text-transform: uppercase;
          color: #c41e3a;
          margin-bottom: 20px;
        }
        .hero-title {
          font-family: 'Fraunces', serif;
          font-optical-sizing: auto;
          font-variation-settings: "SOFT" 50, "WONK" 0;
          font-size: clamp(70px, 10vw, 168px);
          font-weight: 900;
          line-height: 0.86;
          letter-spacing: -5px;
          margin: 0;
        }
        .hero-title em {
          font-style: italic;
          font-weight: 300;
          color: #c41e3a;
          letter-spacing: -3px;
        }
        .hero-lede {
          font-family: 'EB Garamond', serif;
          font-size: 19px;
          line-height: 1.6;
          font-style: italic;
        }
        .hero-lede .drop {
          font-family: 'Fraunces', serif;
          font-weight: 900;
          font-style: normal;
          font-size: 62px;
          float: left;
          line-height: 0.85;
          padding: 6px 10px 0 0;
          color: #c41e3a;
        }
        .byline {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 2.5px;
          text-transform: uppercase;
          color: #666;
          margin-top: 24px;
        }

        .rule-dot::before {
          content: '◆';
          color: #c41e3a;
          margin: 0 14px;
        }
        .section-head {
          display: flex;
          align-items: baseline;
          gap: 24px;
          margin: 80px 0 24px;
        }
        .section-label {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 4px;
          text-transform: uppercase;
          color: #c41e3a;
          white-space: nowrap;
        }
        .section-rule {
          flex: 1;
          height: 1px;
          background: #121010;
        }
        .section-title {
          font-family: 'Fraunces', serif;
          font-size: 42px;
          font-weight: 900;
          letter-spacing: -1.5px;
          line-height: 1;
          margin: 0;
        }
        .section-title em {
          font-style: italic;
          font-weight: 400;
        }

        .columns {
          display: grid;
          grid-template-columns: 2fr 1fr;
          gap: 56px;
          align-items: start;
        }
        @media (max-width: 960px) { .columns { grid-template-columns: 1fr; } }

        .classification {
          width: 100%;
          border-collapse: collapse;
          font-variant-numeric: tabular-nums oldstyle-nums;
        }
        .classification th {
          text-align: left;
          padding: 12px 10px;
          border-bottom: 2px solid #121010;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #666;
          font-weight: 500;
        }
        .classification td {
          padding: 14px 10px;
          border-bottom: 1px dotted #8a857a;
          vertical-align: baseline;
        }
        .classification tr:hover td {
          background: rgba(196, 30, 58, 0.04);
          cursor: pointer;
        }
        .classification tr.selected td {
          background: rgba(196, 30, 58, 0.07);
        }
        .rank {
          font-family: 'Fraunces', serif;
          font-style: italic;
          font-weight: 400;
          font-size: 22px;
          color: #c41e3a;
          width: 60px;
          text-align: right;
          padding-right: 20px;
        }
        .driver-name {
          font-family: 'Fraunces', serif;
          font-size: 22px;
          font-weight: 400;
          letter-spacing: -0.3px;
        }
        .driver-team {
          font-size: 13px;
          font-style: italic;
          color: #666;
          display: block;
        }
        .num-col {
          text-align: right;
          font-family: 'EB Garamond', serif;
          font-size: 19px;
        }
        .prob-top {
          font-weight: 500;
        }
        .col-dist {
          width: 140px;
        }

        .marginalia {
          background: rgba(196, 30, 58, 0.05);
          border-left: 3px solid #c41e3a;
          padding: 24px 26px;
          font-family: 'EB Garamond', serif;
        }
        .marginalia h4 {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: #c41e3a;
          margin: 0 0 12px;
        }
        .marginalia p {
          margin: 0 0 14px;
          font-size: 16px;
          line-height: 1.6;
        }
        .marginalia em { font-style: italic; }

        .pullquote {
          font-family: 'Fraunces', serif;
          font-size: 32px;
          font-style: italic;
          font-weight: 300;
          line-height: 1.2;
          text-align: center;
          max-width: 780px;
          margin: 80px auto;
          color: #121010;
          position: relative;
        }
        .pullquote::before {
          content: '"';
          position: absolute;
          top: -40px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 140px;
          color: #c41e3a;
          line-height: 1;
          font-family: 'Fraunces', serif;
          font-style: italic;
        }
        .pullquote cite {
          display: block;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 3px;
          text-transform: uppercase;
          color: #666;
          font-style: normal;
          margin-top: 20px;
        }

        .shap-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 10px;
        }
        .shap-row {
          display: grid;
          grid-template-columns: 180px 1fr 60px;
          gap: 10px;
          align-items: center;
          font-family: 'EB Garamond', serif;
        }
        .shap-row .feat {
          font-size: 14px;
          font-style: italic;
          color: #222;
        }
        .shap-row .val {
          font-variant-numeric: tabular-nums oldstyle-nums;
          font-size: 14px;
          text-align: right;
        }
        .shap-bar {
          height: 8px;
          background: #eae4d6;
          position: relative;
          border-radius: 1px;
        }
        .shap-bar .pos, .shap-bar .neg {
          position: absolute;
          top: 0;
          bottom: 0;
          background: #121010;
        }
        .shap-bar .pos { left: 50%; background: #1b5e3f; }
        .shap-bar .neg { right: 50%; background: #c41e3a; }
        .shap-bar .mid {
          position: absolute;
          left: 50%;
          top: -2px;
          bottom: -2px;
          width: 1px;
          background: #121010;
        }

        .importance-list {
          list-style: none;
          padding: 0;
          margin: 0;
          counter-reset: feat;
        }
        .importance-list li {
          counter-increment: feat;
          display: grid;
          grid-template-columns: 36px 1fr 60px;
          gap: 14px;
          padding: 10px 0;
          border-bottom: 1px dotted #8a857a;
          align-items: baseline;
        }
        .importance-list li::before {
          content: counter(feat, decimal-leading-zero);
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          color: #c41e3a;
          letter-spacing: 1px;
        }
        .importance-list .ftname {
          font-family: 'EB Garamond', serif;
          font-size: 16px;
          font-style: italic;
        }
        .importance-list .ftval {
          font-variant-numeric: tabular-nums oldstyle-nums;
          font-family: 'EB Garamond', serif;
          font-size: 16px;
          text-align: right;
        }

        .driver-picker {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 20px;
        }
        .driver-picker button {
          background: transparent;
          border: 1px solid #c5bfae;
          padding: 6px 10px;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 1px;
          cursor: pointer;
          color: #121010;
        }
        .driver-picker button.on {
          background: #121010;
          color: #f4f1ea;
          border-color: #121010;
        }

        .colophon {
          margin-top: 100px;
          padding-top: 30px;
          border-top: 3px solid #121010;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: 2px;
          text-transform: uppercase;
          color: #666;
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 20px;
        }
      `}</style>
      <NoiseOverlay />
      <Switcher bg="#f4f1ea" fg="#121010" border="#c5bfae" accent="#c41e3a" />

      <div className="paddock">
        <div className="masthead">
          <span>Volume II · Issue 01</span>
          <span>
            Sakhir <span className="rule-dot" />Round I<span className="rule-dot" /> <span className="red">MMXXVI</span>
          </span>
          <span>The Paddock Gazette</span>
        </div>

        <section className="hero">
          <div>
            <div className="folio">Predictions · Pre-race model · 18 April 2026</div>
            <h1 className="hero-title">
              The Grid,
              <br />
              <em>foretold.</em>
            </h1>
            <div className="byline">
              By the ensemble · verified 5,000 simulations · Xgb·Lgbm·Catb·Net
            </div>
          </div>
          <p className="hero-lede">
            <span className="drop">A</span>
            fter a winter of reset regulations, the model offers its verdict on
            the opening round. Verstappen again — narrowly — with the papayas
            close enough that a safety-car call flips the whole order. What
            follows is the grid as the algorithm dreams it, and why.
          </p>
        </section>

        <section>
          <div className="section-head">
            <span className="section-label">Classification</span>
            <span className="section-rule" />
            <h2 className="section-title">
              The <em>expected</em> order of finish
            </h2>
          </div>

          <div className="columns">
            <table className="classification">
              <thead>
                <tr>
                  <th></th>
                  <th>Driver</th>
                  <th style={{ textAlign: "right" }}>Win</th>
                  <th style={{ textAlign: "right" }}>Podium</th>
                  <th style={{ textAlign: "right" }}>Points</th>
                  <th style={{ textAlign: "right" }}>P10–P90</th>
                  <th className="col-dist">Distribution</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((p, i) => {
                  const hist = DEMO.position_histograms[p.driver_id];
                  return (
                    <tr
                      key={p.driver_id}
                      className={selected === p.driver_id ? "selected" : ""}
                      onClick={() => setSelected(p.driver_id)}
                    >
                      <td className="rank">{ROMAN[i]}.</td>
                      <td>
                        <span className="driver-name">{p.driver_name}</span>
                        <span className="driver-team">{p.team}</span>
                      </td>
                      <td className={`num-col ${i < 3 ? "prob-top" : ""}`}>
                        {(p.win_probability! * 100).toFixed(1)}
                      </td>
                      <td className="num-col">
                        {(p.podium_probability! * 100).toFixed(0)}
                      </td>
                      <td className="num-col">
                        {(p.points_probability! * 100).toFixed(0)}
                      </td>
                      <td className="num-col">
                        {p.position_p10}–{p.position_p90}
                      </td>
                      <td>
                        {hist && <MiniDist hist={hist} predicted={p.predicted_position} />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <aside className="marginalia">
              <h4>Editor's note</h4>
              <p>
                <em>A word on the method.</em> The probabilities in this column
                are not the usual softmax of a ranking score. They come from
                five thousand simulated races, each with its own tyre-wear
                roll, its own safety car, its own mechanical failure.
              </p>
              <p>
                Where the distribution is <em>tight</em>, the model is
                confident. Where it is <em>wide</em>, expect chaos. Lawson's
                distribution stretches from P11 to P19 — make of that what you
                will.
              </p>
              <p>
                Click any driver to read what the algorithm saw.
              </p>
            </aside>
          </div>
        </section>

        <blockquote className="pullquote">
          If the model is right about one thing, it is that pace on long runs
          matters <em>more</em> than a single fast lap — and Verstappen's
          long-run delta in FP2 was decisive.
          <cite>— Ensemble verdict, 14.2% feature weight</cite>
        </blockquote>

        <section>
          <div className="section-head">
            <span className="section-label">Diagnosis</span>
            <span className="section-rule" />
            <h2 className="section-title">
              What the <em>machine</em> saw
            </h2>
          </div>

          <div className="columns">
            <div>
              <div className="driver-picker">
                {predictions.map((p) => (
                  <button
                    key={p.driver_id}
                    className={selected === p.driver_id ? "on" : ""}
                    onClick={() => setSelected(p.driver_id)}
                  >
                    P{p.predicted_position} · {p.driver_id}
                  </button>
                ))}
              </div>

              <div style={{ marginBottom: 14, fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, letterSpacing: 2, textTransform: "uppercase", color: "#c41e3a" }}>
                SHAP attribution — {predictions.find((p) => p.driver_id === selected)?.driver_name}
              </div>

              <div className="shap-grid">
                {selectedShap.map((s) => {
                  const mag = Math.min(1, Math.abs(s.shap_value) / 0.5);
                  const isPositive = s.shap_value >= 0;
                  return (
                    <div key={s.feature} className="shap-row">
                      <span className="feat">{s.feature}</span>
                      <div className="shap-bar">
                        {isPositive ? (
                          <span
                            className="pos"
                            style={{ width: `${mag * 50}%` }}
                          />
                        ) : (
                          <span
                            className="neg"
                            style={{ width: `${mag * 50}%` }}
                          />
                        )}
                        <span className="mid" />
                      </div>
                      <span className="val">
                        {s.shap_value >= 0 ? "+" : ""}
                        {s.shap_value.toFixed(3)}
                      </span>
                    </div>
                  );
                })}
              </div>

              <p style={{ marginTop: 28, fontSize: 15, fontStyle: "italic", color: "#444", maxWidth: 560 }}>
                Green marks features that <em>lifted</em> this driver in the
                ranking; red, those that <em>held him down</em>. A feature
                appears here because it moved this particular prediction more
                than it moved the average driver.
              </p>
            </div>

            <aside>
              <div className="section-label" style={{ marginBottom: 14 }}>
                Global weight
              </div>
              <ol className="importance-list">
                {topFeatures.map((f) => (
                  <li key={f.feature}>
                    <span className="ftname">{f.feature}</span>
                    <span className="ftval">{f.pct.toFixed(1)}%</span>
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </section>

        <div className="colophon">
          <span>The Paddock Gazette · Set in Fraunces &amp; EB Garamond</span>
          <span>{metadata.sessions_used}</span>
          <span>Conf. {metadata.confidence} · {metadata.year} · Round {metadata.round}</span>
        </div>
      </div>
    </>
  );
}
