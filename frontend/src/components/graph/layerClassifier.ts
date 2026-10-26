// ── Layer classification (FILE 3: GitDiagram palette) ────────────────────────
// Classifies a graph node into one of five architecture layers using rules
// over its id + label. Colors sampled from the reference diagram — pastel
// fills with saturated borders. Do not invent new colors here.

export type Layer = "client" | "backend" | "storage" | "external" | "compute";

export interface LayerStyle {
  fill: string;
  border: string;
  text: string;
  icon: string;   // lucide icon name key — resolved in LayerNode
  name: string;
}

export const LAYER_STYLE: Record<Layer, LayerStyle> = {
  client:   { fill: "#DBEAFE", border: "#2563EB", text: "#1E3A8A", icon: "monitor",  name: "Client / UI" },
  backend:  { fill: "#FEF3C7", border: "#D97706", text: "#78350F", icon: "server",   name: "Backend / API" },
  storage:  { fill: "#D1FAE5", border: "#059669", text: "#065F46", icon: "database", name: "Storage / Data" },
  external: { fill: "#FEE2E2", border: "#DC2626", text: "#991B1B", icon: "globe",    name: "External / Integrations" },
  compute:  { fill: "#EDE9FE", border: "#7C3AED", text: "#4C1D95", icon: "cpu",      name: "Compute / Workers" },
};

// Ordered rules — first match wins.
const RULES: Array<{ layer: Layer; re: RegExp }> = [
  // api clients, sdk, integrations, providers
  { layer: "external", re: /(^|\/)(external|integrations?|sdk|providers?)(\/|$)|api[_-]?client|(_|-)client\.|webhook|oauth|payment|stripe|slack|openai|anthropic/i },
  // workers, engines, algorithms, calculations
  { layer: "compute",  re: /worker|engine|algorithm|calculat|comput|scheduler|queue|task|cron/i },
  // models, schemas, migrations, db, persistence
  { layer: "storage",  re: /(^|\/)(models?|schemas?|migrations?|db|database|persistence|repositories?|store|storehouse)(\/|$)|\.(sql|db|sqlite)$/i },
  // services, routes, handlers, controllers, main
  { layer: "backend",  re: /(^|\/)(backend|server|services?|routers?|routes?|handlers?|controllers?|api|middleware|main|app)(\/|$)|\.(py|go|java|rb|php|rs)$/i },
  // UI, components, pages, styles, frontend
  { layer: "client",   re: /(^|\/)(frontend|client|src|components?|pages?|views?|screens?|ui|styles?|assets?|public)(\/|$)|\.(tsx|jsx|vue|svelte|css|scss|html|svg|png|jpg)$/i },
];

/**
 * Classify a node into its architecture layer from its id + label.
 * Extension signals are folded in as a fallback before the final default.
 */
export function classify(id: string, label: string): Layer {
  const hay = `${id} ${label}`;
  for (const { layer, re } of RULES) {
    if (re.test(hay)) return layer;
  }
  // Extension-based fallback for unstructured labels
  if (/\.(tsx|jsx|ts|js|css|html|vue|svelte)$/i.test(hay)) return "client";
  return "backend";
}
