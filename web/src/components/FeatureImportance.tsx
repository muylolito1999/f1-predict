import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PredictResponse, ShapContribution } from "../types";
import { FEATURE_CATEGORIES, categoryFor } from "../theme";

interface Props {
  result: PredictResponse;
}

const TOP_N = 20;

function formatValue(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(3);
}

export default function FeatureImportance({ result }: Props) {
  const {
    feature_importance,
    features_by_driver,
    shap_by_driver,
    predictions,
  } = result;

  const topFeatures = useMemo(
    () =>
      [...feature_importance]
        .sort((a, b) => b.pct - a.pct)
        .slice(0, TOP_N)
        .map((f) => ({ ...f, color: categoryFor(f.feature).color }))
        .reverse(),
    [feature_importance],
  );

  const driverIds = Object.keys(features_by_driver);
  const [selectedDriver, setSelectedDriver] = useState<string>(() => {
    const winner = predictions.find((p) => p.predicted_position === 1);
    return winner?.driver_id ?? driverIds[0] ?? "";
  });

  const grouped = useMemo(() => {
    if (!selectedDriver) return [];
    const row = features_by_driver[selectedDriver] ?? {};
    const out: {
      category: (typeof FEATURE_CATEGORIES)[number];
      values: [string, number | null][];
    }[] = [];
    for (const cat of FEATURE_CATEGORIES) {
      const entries: [string, number | null][] = Object.entries(row)
        .filter(([k]) => cat.match(k))
        .map(([k, v]) => [k, typeof v === "number" ? v : null]);
      if (entries.length) out.push({ category: cat, values: entries });
    }
    return out;
  }, [selectedDriver, features_by_driver]);

  const driverShap: ShapContribution[] = useMemo(() => {
    const list = shap_by_driver?.[selectedDriver] ?? [];
    return [...list]
      .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
      .slice(0, 8)
      .reverse();
  }, [shap_by_driver, selectedDriver]);

  if (!feature_importance.length) {
    return (
      <section className="panel">
        <h2>Feature importance</h2>
        <div className="empty-state">
          No feature importance available for this prediction.
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Feature importance</h2>

      <div style={{ width: "100%", height: Math.max(320, topFeatures.length * 22) }}>
        <ResponsiveContainer>
          <BarChart
            data={topFeatures}
            layout="vertical"
            margin={{ top: 4, right: 24, left: 120, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" horizontal={false} />
            <XAxis
              type="number"
              stroke="#8b949e"
              tick={{ fill: "#8b949e", fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="feature"
              stroke="#8b949e"
              tick={{ fill: "#e6edf3", fontSize: 12 }}
              width={140}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{
                background: "#161b22",
                border: "1px solid #2a3441",
                borderRadius: 6,
                fontSize: 12,
              }}
              formatter={(value: number) => [`${value.toFixed(1)}%`, "Contribution"]}
            />
            <Bar dataKey="pct" radius={[0, 3, 3, 0]}>
              {topFeatures.map((f) => (
                <Cell key={f.feature} fill={f.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="legend">
        {FEATURE_CATEGORIES.map((c) => (
          <span key={c.id}>
            <span className="legend-dot" style={{ background: c.color }} />
            {c.label}
          </span>
        ))}
      </div>

      {driverIds.length > 0 && (
        <div className="features-driver">
          <div className="field" style={{ maxWidth: 320 }}>
            <label>Per-driver explainability</label>
            <select
              value={selectedDriver}
              onChange={(e) => setSelectedDriver(e.target.value)}
            >
              {predictions
                .slice()
                .sort((a, b) => a.predicted_position - b.predicted_position)
                .map((p) => (
                  <option key={p.driver_id} value={p.driver_id}>
                    P{p.predicted_position} — {p.driver_name}
                  </option>
                ))}
            </select>
          </div>

          {driverShap.length > 0 && (
            <div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--text-dim)",
                  textTransform: "uppercase",
                  letterSpacing: 0.4,
                  margin: "6px 0",
                }}
              >
                SHAP — why the model ranked this driver here
              </div>
              <div style={{ width: "100%", height: Math.max(180, driverShap.length * 28) }}>
                <ResponsiveContainer>
                  <BarChart
                    data={driverShap}
                    layout="vertical"
                    margin={{ top: 4, right: 24, left: 120, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" horizontal={false} />
                    <XAxis
                      type="number"
                      stroke="#8b949e"
                      tick={{ fill: "#8b949e", fontSize: 11 }}
                    />
                    <YAxis
                      type="category"
                      dataKey="feature"
                      stroke="#8b949e"
                      tick={{ fill: "#e6edf3", fontSize: 12 }}
                      width={140}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                      contentStyle={{
                        background: "#161b22",
                        border: "1px solid #2a3441",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                      formatter={(value: number) => [
                        value.toFixed(3),
                        value >= 0 ? "Lifts ranking" : "Hurts ranking",
                      ]}
                    />
                    <Bar dataKey="shap_value" radius={[0, 3, 3, 0]}>
                      {driverShap.map((f) => (
                        <Cell
                          key={f.feature}
                          fill={f.shap_value >= 0 ? "#2ea043" : "#da3633"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div
            style={{
              fontSize: 12,
              color: "var(--text-dim)",
              textTransform: "uppercase",
              letterSpacing: 0.4,
              margin: "10px 0 -2px",
            }}
          >
            Raw feature values
          </div>
          {grouped.map(({ category, values }) => (
            <details key={category.id} className="features-group">
              <summary>
                <span className="legend-dot" style={{ background: category.color }} />
                {category.label} · {values.length} features
              </summary>
              <table>
                <tbody>
                  {values.map(([name, value]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{formatValue(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}
