interface Props {
  size?: number;
  animated?: boolean;
}

export function MitsMark({ size = 28, animated = true }: Props) {
  return (
    <span
      className="inline-block"
      style={{ width: size, height: size }}
      aria-label="MITS"
    >
      <svg viewBox="0 0 32 32" fill="none" width="100%" height="100%">
        <defs>
          <linearGradient id="mits-grad" x1="0" y1="0" x2="32" y2="32">
            <stop offset="0%" stopColor="#a583ff" />
            <stop offset="100%" stopColor="#e8c668" />
          </linearGradient>
        </defs>
        <polygon
          points="16,2 28,9 28,23 16,30 4,23 4,9"
          stroke="url(#mits-grad)"
          strokeWidth="1.3"
          fill="none"
          style={animated ? { animation: "float 4s ease-in-out infinite" } : undefined}
        />
        <polygon
          points="16,8 23,22 9,22"
          stroke="#a583ff"
          strokeWidth="1"
          fill="rgba(165,131,255,0.12)"
        />
        <circle cx="16" cy="18" r="2.2" fill="#e8c668" style={{ filter: "drop-shadow(0 0 3px #e8c668)" }} />
        <line x1="16" y1="2" x2="16" y2="5" stroke="#e8c668" strokeWidth="1.2" />
        <line x1="4" y1="9" x2="7" y2="10.5" stroke="#a583ff" strokeWidth="1" />
        <line x1="28" y1="9" x2="25" y2="10.5" stroke="#a583ff" strokeWidth="1" />
      </svg>
    </span>
  );
}
