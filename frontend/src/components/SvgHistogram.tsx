interface Props {
  bins: (string | number)[];
  counts: number[];
  width?: number;
  height?: number;
  xLabel?: string;
}

/** Hand-rolled SVG histogram — no chart libraries, fully offline. */
export default function SvgHistogram({ bins, counts, width = 560, height = 280, xLabel }: Props) {
  const padL = 48;
  const padB = 44;
  const padT = 12;
  const padR = 12;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const max = Math.max(1, ...counts);
  const n = Math.max(1, counts.length);
  const barW = innerW / n;
  const ticks = 4;

  const fmt = (b: string | number) =>
    typeof b === 'number' ? (Math.abs(b) >= 100 ? b.toFixed(0) : b.toFixed(2)) : b;

  return (
    <svg width={width} height={height} role="img" aria-label="histogram">
      {Array.from({ length: ticks + 1 }, (_, t) => {
        const v = (max * t) / ticks;
        const y = padT + innerH - (innerH * t) / ticks;
        return (
          <g key={t}>
            <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="#d9e1ea" strokeWidth={1} />
            <text x={padL - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#5d6f84">
              {Math.round(v)}
            </text>
          </g>
        );
      })}
      {counts.map((c, i) => {
        const h = (innerH * c) / max;
        const x = padL + barW * i + 1;
        const y = padT + innerH - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={Math.max(barW - 2, 1)} height={Math.max(h, 1)} fill="#14335a">
              <title>{`bin ${fmt(bins[i] ?? i)}: ${c}`}</title>
            </rect>
            {n <= 20 && (
              <text
                x={x + barW / 2}
                y={padT + innerH + 14}
                textAnchor="middle"
                fontSize={9}
                fill="#5d6f84"
              >
                {fmt(bins[i] ?? i)}
              </text>
            )}
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
