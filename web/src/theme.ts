// Canonical F1 team colors (2024/25/26 era). Keys matched case-insensitively
// against team names coming from the backend.
const TEAM_COLORS: Record<string, string> = {
  "red bull": "#1e2d5f",
  "red bull racing": "#1e2d5f",
  "ferrari": "#dc0000",
  "mercedes": "#00d7b6",
  "mclaren": "#ff8700",
  "aston martin": "#006f62",
  "alpine": "#0090ff",
  "williams": "#005aff",
  "rb": "#6692ff",
  "racing bulls": "#6692ff",
  "visa cash app rb": "#6692ff",
  "sauber": "#52e252",
  "kick sauber": "#52e252",
  "stake": "#52e252",
  "haas": "#b6babd",
  "audi": "#ee3126",
  "cadillac": "#c99a4d",
};

export function teamColor(team: string | undefined | null): string {
  if (!team) return "#6b7280";
  const key = team.toLowerCase();
  for (const [k, v] of Object.entries(TEAM_COLORS)) {
    if (key.includes(k)) return v;
  }
  return "#6b7280";
}

// Feature category palette. Each category has a display label, color, and a
// matcher against the FEATURE_COLUMNS names defined in src/features/builder.py.
export interface FeatureCategory {
  id: string;
  label: string;
  color: string;
  match: (feat: string) => boolean;
}

export const FEATURE_CATEGORIES: FeatureCategory[] = [
  { id: "practice", label: "Practice", color: "#58a6ff", match: (f) => f.startsWith("fp_") },
  { id: "driver", label: "Driver", color: "#f778ba", match: (f) => f.startsWith("driver_") },
  { id: "team", label: "Team", color: "#d29922", match: (f) => f.startsWith("team_") },
  { id: "circuit", label: "Circuit", color: "#a371f7", match: (f) => f.startsWith("circuit_") },
  { id: "weather", label: "Weather", color: "#39d0d8", match: (f) => f.startsWith("race_") },
  { id: "strategy", label: "Strategy", color: "#7ee787", match: (f) =>
    f.startsWith("tyre_") ||
    f === "expected_pit_stops" ||
    f === "optimal_compound_advantage" ||
    f === "undercut_potential" ||
    f === "starting_tyre_compound",
  },
  { id: "news", label: "News / Upgrades", color: "#ff7b72", match: (f) =>
    f.startsWith("upgrade_") || f === "team_media_confidence" || f === "regulation_compliance_flag",
  },
];

export function categoryFor(feature: string): FeatureCategory {
  for (const cat of FEATURE_CATEGORIES) {
    if (cat.match(feature)) return cat;
  }
  return { id: "other", label: "Other", color: "#6b7280", match: () => true };
}
