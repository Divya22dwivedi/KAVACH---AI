interface Props {
  items: { label: string; value: number }[];
  width?: number;
  height?: number;
  xLabel?: string;
}

/** Hand-rolled SVG bar chart — no chart libraries, fully offline. */
export default function SvgBarChart({ items, width = 560, height = 280, xLabel }: Props) {
  const padL = 48;
  const padB = 44;
  const padT = 12;
  const padR = 12;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const max = Math.max(1, ...items.map((i) => i.value));
  const n = Math.max(1, items.length);
  const slot = innerW / n;
  const barW = Math.min(56, slot * 0.6);

  const ticks = 4;
  return (
    <svg width={width} height={height} role="img" aria-label="bar chart">
      {Array.from({ length: ticks + 1 }, (_, t) => {
        const v = (max * t) / ticks;
        const y = padT + innerH - (innerH * t) / ticks;
        return (
          <g key={t}>
            <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="#d9e1ea" strokeWidth={1} />
            <text x={padL - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#5d6f84">
              {v >= 100 ? Math.round(v) : v.toFixed(1)}
            </text>
          </g>
        );
      })}
      {items.map((it, i) => {
        const h = (innerH * it.value) / max;
        const x = padL + slot * i + (slot - barW) / 2;
        const y = padT + innerH - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={Math.max(h, 1)} fill="#1d5fb8" rx={2}>
              <title>{`${it.label}: ${it.value}`}</title>
            </rect>
            <text
              x={x + barW / 2}
              y={padT + innerH + 14}
              textAnchor="middle"
              fontSize={10}
              fill="#5d6f84"
            >
              {it.label.length > 14 ? `${it.label.slice(0, 13)}…` : it.label}
            </text>
          </g>
        );
      })}
      {xLabel && (
        <text x={padL + innerW / 2} y={height - 4} textAnchor="middle" fontSize={11} fill="#5d6f84">
          {xLabel}
        </text>
      )}
    </svg>
  );
}
