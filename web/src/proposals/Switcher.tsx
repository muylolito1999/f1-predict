import { useHashRoute } from "./useHashRoute";

const PROPOSALS = [
  { slug: "live", label: "00 · Official" },
  { slug: "paddock", label: "01 · Paddock" },
  { slug: "telemetry", label: "02 · Telemetry" },
  { slug: "circuit", label: "03 · Circuit" },
  { slug: "nocturne", label: "04 · Nocturne" },
  { slug: "slipstream", label: "05 · Slipstream" },
];

interface Props {
  /** background colour for the chip — choose to match the host proposal. */
  bg?: string;
  fg?: string;
  border?: string;
  accent?: string;
}

/** Fixed top-right chip that lets the user hop between proposals without
 *  returning to the gallery. Styled per-proposal via the colour props. */
export default function Switcher({
  bg = "#111",
  fg = "#fff",
  border = "#333",
  accent = "#e10600",
}: Props) {
  const [route, go] = useHashRoute();

  return (
    <div
      style={{
        position: "fixed",
        top: 18,
        right: 18,
        zIndex: 1000,
        display: "flex",
        gap: 6,
        alignItems: "center",
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 2,
        padding: "6px 6px 6px 10px",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        letterSpacing: 1,
        color: fg,
      }}
    >
      <button
        onClick={() => go("")}
        style={{
          background: "transparent",
          border: 0,
          color: fg,
          cursor: "pointer",
          fontFamily: "inherit",
          fontSize: "inherit",
          padding: "4px 6px",
          letterSpacing: 1,
        }}
      >
        ← Index
      </button>
      <span style={{ opacity: 0.3 }}>│</span>
      {PROPOSALS.map((p) => (
        <button
          key={p.slug}
          onClick={() => go(p.slug)}
          style={{
            background: route === p.slug ? accent : "transparent",
            color: route === p.slug ? "#fff" : fg,
            border: 0,
            cursor: "pointer",
            fontFamily: "inherit",
            fontSize: 10,
            padding: "4px 8px",
            letterSpacing: 1,
            borderRadius: 2,
          }}
          title={p.label}
        >
          {p.label.split(" · ")[0]}
        </button>
      ))}
    </div>
  );
}
