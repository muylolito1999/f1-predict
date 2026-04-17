interface Props {
  histogram: number[];
  color: string;
  predicted?: number;
  width?: number;
  height?: number;
}

/** Tiny SVG sparkline showing a simulated finish-position distribution. */
export default function PositionSpark({
  histogram,
  color,
  predicted,
  width = 100,
  height = 22,
}: Props) {
  if (!histogram?.length) return null;
  const max = Math.max(...histogram) || 1;
  const n = histogram.length;
  const barW = width / n;
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {histogram.map((c, i) => {
        const h = (c / max) * (height - 2);
        const x = i * barW;
        const y = height - h;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(1, barW - 0.5)}
            height={h}
            fill={color}
            opacity={0.75}
          />
        );
      })}
      {predicted != null && (
        <line
          x1={(predicted - 0.5) * barW}
          x2={(predicted - 0.5) * barW}
          y1={0}
          y2={height}
          stroke="#e6edf3"
          strokeWidth={1}
          opacity={0.7}
        />
      )}
    </svg>
  );
}
