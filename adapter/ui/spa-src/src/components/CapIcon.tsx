// Iconos SVG por entity_type (sin emoji) para el panel de capacidades.

interface Props {
  entityType: string;
  color?: string;
}

export function CapIcon({ entityType, color = "currentColor" }: Props) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  switch (entityType) {
    case "vehicle":
      return (
        <svg {...common}>
          <path d="M5 17h14v-5l-2-5H7l-2 5v5z" />
          <circle cx="7.5" cy="17" r="1.5" />
          <circle cx="16.5" cy="17" r="1.5" />
        </svg>
      );
    case "object":
      return (
        <svg {...common}>
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <path d="M4 10h16M10 4v16" />
        </svg>
      );
    case "face":
    case "face_id":
      return (
        <svg {...common}>
          <circle cx="12" cy="9" r="4" />
          <path d="M6 20c1.5-3 4-4.5 6-4.5S16.5 17 18 20" />
        </svg>
      );
    case "scene":
      return (
        <svg {...common}>
          <path d="M3 18h18M4 18l5-8 4 5 3-4 4 7" />
        </svg>
      );
    case "pose":
      return (
        <svg {...common}>
          <circle cx="12" cy="5" r="2" />
          <path d="M12 7v6M8 10l4 3 4-3M10 21l2-8 2 8" />
        </svg>
      );
    case "text":
      return (
        <svg {...common}>
          <path d="M5 5h14M12 5v14M8 19h8" />
        </svg>
      );
    case "sign":
      return (
        <svg {...common}>
          <path d="M12 3l9 16H3L12 3z" />
          <path d="M12 10v4M12 16h.01" />
        </svg>
      );
    case "open_vocab":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="6" />
          <path d="M20 20l-4-4" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="7" />
        </svg>
      );
  }
}
