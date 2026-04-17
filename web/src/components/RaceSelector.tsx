import { useEffect, useState } from "react";
import { listRaces } from "../api";
import type { Race } from "../types";

interface Props {
  year: number;
  round: number | null;
  onYearChange: (year: number) => void;
  onRoundChange: (round: number) => void;
}

const YEARS = [2022, 2023, 2024, 2025, 2026];

export default function RaceSelector({ year, round, onYearChange, onRoundChange }: Props) {
  const [races, setRaces] = useState<Race[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listRaces(year)
      .then((r) => {
        if (!cancelled) setRaces(r);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [year]);

  return (
    <>
      <div className="field">
        <label>Year</label>
        <select value={year} onChange={(e) => onYearChange(Number(e.target.value))}>
          {YEARS.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Race</label>
        <select
          value={round ?? ""}
          onChange={(e) => onRoundChange(Number(e.target.value))}
          disabled={loading || !!err}
        >
          <option value="" disabled>
            {loading ? "Loading…" : err ? "Unavailable" : "Select a race"}
          </option>
          {races.map((r) => (
            <option key={r.round} value={r.round}>
              R{r.round} — {r.name}
            </option>
          ))}
        </select>
        {err && <span className="error" style={{ fontSize: 12 }}>{err}</span>}
      </div>
    </>
  );
}
