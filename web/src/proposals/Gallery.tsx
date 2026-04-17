import { useHashRoute } from "./useHashRoute";

interface Proposal {
  slug: string;
  index: string;
  title: string;
  tagline: string;
  description: string;
  palette: string[];
  fonts: string;
  preview: (i: number) => React.ReactNode;
}

const PROPOSALS: Proposal[] = [
  {
    slug: "paddock",
    index: "01",
    title: "Paddock",
    tagline: "Editorial · Magazine",
    description:
      "Cream paper stock, ink serifs, blood-red accents. Reads like a post-race classification in a 1976 programme.",
    palette: ["#f4f1ea", "#0a0a0a", "#c41e3a", "#b8985a"],
    fonts: "Fraunces · EB Garamond",
    preview: () => (
      <div
        style={{
          background: "#f4f1ea",
          padding: "22px 18px",
          fontFamily: "'EB Garamond', serif",
          color: "#0a0a0a",
          height: "100%",
        }}
      >
        <div style={{ fontSize: 10, letterSpacing: 3, textTransform: "uppercase", color: "#c41e3a" }}>
          Folio 01 · Bahrain
        </div>
        <div style={{ fontFamily: "'Fraunces', serif", fontSize: 34, fontWeight: 900, lineHeight: 1, margin: "8px 0" }}>
          The Grid,
          <br />
          <em style={{ fontStyle: "italic", fontWeight: 400 }}>foretold</em>
        </div>
        <div style={{ borderTop: "1px solid #0a0a0a", margin: "10px 0", paddingTop: 6, fontSize: 11 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span><b>i.</b>&nbsp;&nbsp;Verstappen</span>
            <span>34.0%</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span><b>ii.</b>&nbsp;&nbsp;Norris</span>
            <span>21.0%</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span><b>iii.</b>&nbsp;&nbsp;Leclerc</span>
            <span>15.0%</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    slug: "telemetry",
    index: "02",
    title: "Telemetry",
    tagline: "Brutalist · Terminal",
    description:
      "Monospace-only phosphor readout. ASCII frames, CRT scanlines, blinking cursor. Looks like the engineer's pit wall.",
    palette: ["#000000", "#00ff6a", "#ffb000", "#ff0040"],
    fonts: "IBM Plex Mono",
    preview: () => (
      <div
        style={{
          background: "#000",
          color: "#00ff6a",
          padding: 14,
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10,
          lineHeight: 1.3,
          height: "100%",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0, rgba(0,0,0,0.18) 1px, transparent 1px, transparent 3px)",
            pointerEvents: "none",
          }}
        />
        <div>┌─ PREDICT ── BAH R1 ──────┐</div>
        <div>│ [OK] FP1·FP2·FP3 loaded  │</div>
        <div>│ [OK] 5000 sims · σ=0.25  │</div>
        <div>│ ─────────────────────────│</div>
        <div>│ P01 VER  34.0%  ████████ │</div>
        <div>│ P02 NOR  21.0%  █████    │</div>
        <div style={{ color: "#ffb000" }}>│ P03 LEC  15.0%  ███░     │</div>
        <div style={{ color: "#ff0040" }}>│ DNF risk 08.4%  LAW OCO  │</div>
        <div>└──────────────────────────┘</div>
        <div style={{ color: "#00ff6a" }}>▌</div>
      </div>
    ),
  },
  {
    slug: "circuit",
    index: "03",
    title: "Circuit",
    tagline: "Heritage · Racing poster",
    description:
      "Livery stripes in Gulf blue and papaya, chunky condensed caps, racing roundels. A 1970s race-weekend poster.",
    palette: ["#f4e8d0", "#00a3ff", "#ff6400", "#1a1a1a"],
    fonts: "Bebas Neue · DM Sans",
    preview: () => (
      <div
        style={{
          background: "#f4e8d0",
          height: "100%",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 14, background: "#00a3ff" }} />
        <div style={{ position: "absolute", top: 14, left: 0, right: 0, height: 8, background: "#ff6400" }} />
        <div style={{ padding: "34px 16px 16px" }}>
          <div
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: 38,
              lineHeight: 0.9,
              letterSpacing: 1,
              color: "#1a1a1a",
            }}
          >
            BAHRAIN
            <br />
            GRAND PRIX
          </div>
          <div
            style={{
              display: "flex",
              gap: 6,
              marginTop: 14,
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 10,
              fontWeight: 600,
            }}
          >
            <span style={{ background: "#1a1a1a", color: "#f4e8d0", padding: "4px 8px", borderRadius: 999 }}>
              1 · VER
            </span>
            <span style={{ background: "#ff6400", color: "#1a1a1a", padding: "4px 8px", borderRadius: 999 }}>
              2 · NOR
            </span>
            <span style={{ background: "#00a3ff", color: "#1a1a1a", padding: "4px 8px", borderRadius: 999 }}>
              3 · LEC
            </span>
          </div>
        </div>
      </div>
    ),
  },
  {
    slug: "nocturne",
    index: "04",
    title: "Nocturne",
    tagline: "Luxury · Monaco at night",
    description:
      "Midnight navy, champagne gold, thin editorial serifs, hairline rules, foil shimmer. VIP terrace after dark.",
    palette: ["#0a1628", "#d4af37", "#f5f0e8", "#000000"],
    fonts: "Instrument Serif · Cormorant",
    preview: () => (
      <div
        style={{
          background: "linear-gradient(160deg, #0a1628 0%, #04080f 100%)",
          height: "100%",
          padding: 18,
          color: "#f5f0e8",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            width: 80,
            height: 80,
            borderRadius: "50%",
            right: -20,
            top: -20,
            background: "radial-gradient(circle, rgba(212,175,55,0.4) 0%, transparent 70%)",
          }}
        />
        <div style={{ fontSize: 9, letterSpacing: 4, color: "#d4af37", textTransform: "uppercase" }}>
          mmxxvi · round 1
        </div>
        <div
          style={{
            fontFamily: "'Instrument Serif', serif",
            fontSize: 38,
            lineHeight: 1,
            fontWeight: 400,
            margin: "14px 0 8px",
            letterSpacing: -0.5,
          }}
        >
          Bahrain
          <br />
          <em style={{ fontStyle: "italic", color: "#d4af37" }}>Grand Prix</em>
        </div>
        <div style={{ height: 1, background: "linear-gradient(90deg, #d4af37, transparent)", margin: "10px 0" }} />
        <div style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 12, opacity: 0.75 }}>
          <span style={{ color: "#d4af37" }}>I.</span> M. Verstappen — 34.0
          <br />
          <span style={{ color: "#d4af37" }}>II.</span> L. Norris — 21.0
        </div>
      </div>
    ),
  },
  {
    slug: "slipstream",
    index: "05",
    title: "Slipstream",
    tagline: "Kinetic · Pure speed",
    description:
      "F1 red and tungsten black, slashed diagonals, condensed display caps, motion streaks, scrolling marquee. Aggressive.",
    palette: ["#e10600", "#0d0d0d", "#ffffff", "#f4c430"],
    fonts: "Anton · Barlow",
    preview: () => (
      <div
        style={{
          background: "#0d0d0d",
          height: "100%",
          padding: 0,
          position: "relative",
          overflow: "hidden",
          color: "#fff",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(105deg, transparent 0%, transparent 42%, #e10600 42%, #e10600 55%, transparent 55%)",
          }}
        />
        <div style={{ position: "relative", padding: "14px 14px 0" }}>
          <div
            style={{
              fontFamily: "'Anton', sans-serif",
              fontSize: 50,
              lineHeight: 0.85,
              fontWeight: 400,
              letterSpacing: -1,
              textTransform: "uppercase",
              transform: "skew(-6deg)",
            }}
          >
            SECTOR
            <br />
            <span style={{ color: "#e10600" }}>ONE</span>
          </div>
          <div
            style={{
              fontFamily: "'Barlow Semi Condensed', sans-serif",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: 2,
              marginTop: 10,
              textTransform: "uppercase",
            }}
          >
            01 VER · 02 NOR · 03 LEC
          </div>
        </div>
      </div>
    ),
  },
];

export default function Gallery() {
  const [, go] = useHashRoute();

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,900;1,9..144,400&family=EB+Garamond:ital,wght@0,400;1,400&family=IBM+Plex+Mono:wght@400;500;700&family=Bebas+Neue&family=DM+Sans:opsz,wght@9..40,400;9..40,600;9..40,700&family=Instrument+Serif:ital@0;1&family=Cormorant+Garamond:ital,wght@0,400;1,400&family=Anton&family=Barlow+Semi+Condensed:wght@400;600;700;900&display=swap');

        .gallery {
          min-height: 100vh;
          background:
            radial-gradient(ellipse at 20% 0%, rgba(225,6,0,0.08), transparent 50%),
            radial-gradient(ellipse at 80% 100%, rgba(212,175,55,0.05), transparent 50%),
            #0b0e13;
          color: #e6edf3;
          padding: 80px 40px 120px;
          font-family: 'DM Sans', sans-serif;
        }
        .gallery-inner {
          max-width: 1360px;
          margin: 0 auto;
        }
        .gallery-eyebrow {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 4px;
          text-transform: uppercase;
          color: #8b949e;
        }
        .gallery-title {
          font-family: 'Fraunces', serif;
          font-size: clamp(48px, 7vw, 88px);
          font-weight: 900;
          line-height: 0.95;
          letter-spacing: -2px;
          margin: 20px 0 10px;
          max-width: 900px;
        }
        .gallery-title em {
          font-style: italic;
          font-weight: 400;
          color: #e10600;
        }
        .gallery-sub {
          font-family: 'Cormorant Garamond', serif;
          font-size: 20px;
          max-width: 640px;
          line-height: 1.5;
          color: #a9b4c0;
          margin-bottom: 60px;
        }

        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
          gap: 24px;
        }

        .card {
          background: #11151d;
          border: 1px solid #1e2430;
          border-radius: 4px;
          overflow: hidden;
          cursor: pointer;
          transition: transform 200ms ease, border-color 200ms ease;
          display: flex;
          flex-direction: column;
        }
        .card:hover {
          transform: translateY(-4px);
          border-color: #e10600;
        }
        .card-preview {
          height: 220px;
          overflow: hidden;
          border-bottom: 1px solid #1e2430;
          position: relative;
        }
        .card-body {
          padding: 22px 22px 24px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .card-meta {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
        }
        .card-index {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          letter-spacing: 3px;
          color: #8b949e;
        }
        .card-fonts {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          color: #8b949e;
          letter-spacing: 1px;
        }
        .card-title {
          font-family: 'Fraunces', serif;
          font-size: 32px;
          font-weight: 900;
          letter-spacing: -1px;
          margin: 0;
        }
        .card-tag {
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 2px;
          color: #e10600;
          font-weight: 600;
        }
        .card-desc {
          font-size: 14px;
          line-height: 1.55;
          color: #a9b4c0;
          margin: 4px 0 14px;
        }
        .card-palette {
          display: flex;
          gap: 4px;
        }
        .palette-swatch {
          width: 24px;
          height: 24px;
          border-radius: 2px;
        }
        .card-cta {
          margin-top: 14px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 2px;
          color: #e6edf3;
        }
        .card:hover .card-cta {
          color: #e10600;
        }
        .arrow {
          display: inline-block;
          transition: transform 150ms ease;
        }
        .card:hover .arrow {
          transform: translateX(4px);
        }

        .footer-note {
          margin-top: 80px;
          padding-top: 30px;
          border-top: 1px solid #1e2430;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          color: #6b7684;
          display: flex;
          gap: 30px;
          flex-wrap: wrap;
        }
      `}</style>

      <div className="gallery">
        <div className="gallery-inner">
          <div className="gallery-eyebrow">F1 Predict · UI studies · 2026</div>
          <h1 className="gallery-title">
            Five directions for a dashboard that tells the <em>truth</em> about race day.
          </h1>
          <p className="gallery-sub">
            Same data — ensemble scores, Monte Carlo distributions, SHAP
            attributions — five interpretations. Pick one, or cherry-pick the
            moves that feel right.
          </p>

          <div className="grid">
            {PROPOSALS.map((p, i) => (
              <div key={p.slug} className="card" onClick={() => go(p.slug)}>
                <div className="card-preview">{p.preview(i)}</div>
                <div className="card-body">
                  <div className="card-meta">
                    <span className="card-index">No. {p.index}</span>
                    <span className="card-fonts">{p.fonts}</span>
                  </div>
                  <div className="card-tag">{p.tagline}</div>
                  <h2 className="card-title">{p.title}</h2>
                  <p className="card-desc">{p.description}</p>
                  <div className="card-palette">
                    {p.palette.map((c) => (
                      <span
                        key={c}
                        className="palette-swatch"
                        style={{ background: c, border: c === "#000000" ? "1px solid #333" : "none" }}
                      />
                    ))}
                  </div>
                  <span className="card-cta">
                    Open proposal <span className="arrow">→</span>
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="footer-note">
            <span>20 drivers · 5000 Monte-Carlo sims · 56 features</span>
            <span>2026 Bahrain Grand Prix · Round 1</span>
            <span>Click a card to enter →</span>
          </div>
        </div>
      </div>
    </>
  );
}
