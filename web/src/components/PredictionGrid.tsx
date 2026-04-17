import type { PredictResponse } from "../types";
import { teamColor } from "../theme";
import PositionSpark from "./PositionSpark";

interface Props {
  result: PredictResponse;
}

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function num(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function positionClass(pos: number): string {
  if (pos <= 3) return "pos-podium";
  if (pos <= 10) return "pos-points";
  return "pos-dim";
}

export default function PredictionGrid({ result }: Props) {
  const { predictions, metadata, position_histograms } = result;
  const title = metadata.race_name
    ? `${metadata.year ?? ""} ${metadata.race_name}`.trim()
    : "Race prediction";

  const sorted = [...predictions].sort(
    (a, b) => a.predicted_position - b.predicted_position,
  );

  const hasSim = sorted.some((r) => r.expected_position != null);
  const hasHist = Object.keys(position_histograms).length > 0;

  return (
    <section className="panel">
      <h2>{title}</h2>

      <table className="grid">
        <thead>
          <tr>
            <th style={{ width: 40 }}>P</th>
            <th>Driver</th>
            <th>Team</th>
            <th className="num">Win</th>
            <th className="num">Podium</th>
            <th className="num">Points</th>
            {hasSim && <th className="num">Expected</th>}
            {hasSim && <th>Range (P10–P90)</th>}
            {hasHist && <th>Distribution</th>}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const pos = row.predicted_position;
            const color = teamColor(row.team);
            const hist = position_histograms[row.driver_id];
            return (
              <tr key={row.driver_id} className={positionClass(pos)}>
                <td className="num">{pos}</td>
                <td>
                  <div className="driver-cell">
                    <span className="team-stripe" style={{ background: color }} />
                    {row.driver_name}
                  </div>
                </td>
                <td>{row.team}</td>
                <td className="num">{pct(row.win_probability)}</td>
                <td className="num">{pct(row.podium_probability)}</td>
                <td className="num">{pct(row.points_probability)}</td>
                {hasSim && (
                  <td className="num">{num(row.expected_position)}</td>
                )}
                {hasSim && (
                  <td>
                    {row.position_p10 != null && row.position_p90 != null
                      ? `P${Math.round(row.position_p10)} – P${Math.round(row.position_p90)}`
                      : "—"}
                  </td>
                )}
                {hasHist && (
                  <td>
                    {hist ? (
                      <PositionSpark
                        histogram={hist}
                        color={color}
                        predicted={pos}
                      />
                    ) : (
                      "—"
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="footer-meta" style={{ marginTop: 12 }}>
        <span>
          <strong>Sessions:</strong> {metadata.sessions_used || "—"}
        </span>
        <span>
          <strong>Model confidence:</strong> {metadata.confidence || "—"}
        </span>
        <span>
          <strong>Round:</strong> {metadata.round ?? "—"}
        </span>
        {hasHist && (
          <span style={{ color: "var(--text-dim)" }}>
            Distribution: Monte Carlo finish positions (1 → 20, left → right);
            vertical bar = predicted rank.
          </span>
        )}
      </div>
    </section>
  );
}
