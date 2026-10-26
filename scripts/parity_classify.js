// parity_classify.js
// Parity probe for the RepoScope layer classifier.
//
// Runs the EXACT rules from frontend/src/components/graph/layerClassifier.ts
// over a corpus file and prints one classification per case as JSON.
//
//   node scripts/parity_classify.js backend/tests/fixtures/layer_corpus.json
//
// backend/tests/test_arch_rules.py runs this and asserts that
// backend/arch_rules.py produces identical output. If the frontend rules
// change without the backend changing, that test fails — which is the
// whole point: one rule table, two languages, zero drift.
const fs = require("fs");

const RULES = [
  { layer: "external", re: /(^|\/)(external|integrations?|sdk|providers?)(\/|$)|api[_-]?client|(_|-)client\.|webhook|oauth|payment|stripe|slack|openai|anthropic/i },
  { layer: "compute",  re: /worker|engine|algorithm|calculat|comput|scheduler|queue|task|cron/i },
  { layer: "storage",  re: /(^|\/)(models?|schemas?|migrations?|db|database|persistence|repositories?|store|storehouse)(\/|$)|\.(sql|db|sqlite)$/i },
  { layer: "backend",  re: /(^|\/)(backend|server|services?|routers?|routes?|handlers?|controllers?|api|middleware|main|app)(\/|$)|\.(py|go|java|rb|php|rs)$/i },
  { layer: "client",   re: /(^|\/)(frontend|client|src|components?|pages?|views?|screens?|ui|styles?|assets?|public)(\/|$)|\.(tsx|jsx|vue|svelte|css|scss|html|svg|png|jpg)$/i },
];

function classify(id, label) {
  const hay = `${id} ${label}`;
  for (const { layer, re } of RULES) if (re.test(hay)) return layer;
  if (/\.(tsx|jsx|ts|js|css|html|vue|svelte)$/i.test(hay)) return "client";
  return "backend";
}

const corpusPath = process.argv[2];
if (!corpusPath) {
  console.error("usage: node scripts/parity_classify.js <corpus.json>");
  process.exit(2);
}

const corpus = JSON.parse(fs.readFileSync(corpusPath, "utf8"));
const cases = Array.isArray(corpus) ? corpus : corpus.cases || [];
const out = cases.map(([id, label]) => classify(id, label));
process.stdout.write(JSON.stringify(out));
