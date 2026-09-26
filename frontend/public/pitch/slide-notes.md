# Slide Notes — RepoScope Pitch Deck

Per-slide talking points, timings, and Q&A ammo for the live pitch.

## Slide 1 — Title (0:15)
Open on the logo. One line: "We make codebases explain themselves."
Mention: built for the IBM Bob 2.0 Hackathon on lablab.ai.

## Slide 2 — Problem (0:30)
Ask the judges: "How long until you can answer a question in an unfamiliar
repo with confidence?" The pain: five tools, zero citations, hallucinated
answers from generic chatbots. Emphasize *trust* — generic LLMs guess.

## Slide 3 — Insight (0:25)
The knowledge graph is the product. Every codebase question reduces to
what/where/what-touches-it/what-changed. One graph answers all four.

## Slide 4 — Solution (0:40)
This is the real app screenshot — point at the three zones: file tree left,
layered graph center, chat below. Stress "paste a URL, seconds to first
answer." All demo repos are real public GitHub projects.

## Slide 5 — Features (0:30)
Don't read the grid — pick three: Code Tours (guided onboarding), Impact
Analysis (blast radius before you merge), Reverse Build Prompt (repo → agent
brief). The rest get one breath.

## Slide 6 — Architecture (0:30)
React + Vite frontend, FastAPI backend, SSE streaming throughout, MCP
servers for GitHub + code memory, and a rotating LLM chain
(OpenRouter → Groq → NVIDIA NIM) that survives rate limits by rotating
multiple keys per provider. Health endpoint exposes uptime and key counts.

## Slide 7 — Why it wins (0:25)
Comparison: each existing tool does one thing; none share ground truth.
RepoScope's graph is the shared truth every feature reads from.

## Slide 8 — Built with AI (0:30)
Honest split: IBM Bob drove most tasks across 8 sessions (screenshots are
Bob's real task summaries); Z Code paired on the complex debugging — the
graph layout root-cause fix is a good war story (diagnosed with instrumented
logging before touching code).

## Slide 9 — Demo highlights (0:20)
Three one-liners over three real screenshots. If live demo time is short,
this slide IS the backup demo.

## Slide 10 — CTA (0:15)
Repo is public, demo repos are one click inside the app, judges can paste
any repo URL. Close with the tagline.

## Likely judge questions
- **Private repos?** BYOK — paste a GitHub PAT; stored in memory only.
- **LLM costs?** Free-tier first (OpenRouter free models), multi-key
  rotation, NVIDIA NIM fallback. Bring your own keys.
- **Big repos?** Node cap with directory grouping, `onlyRenderVisibleElements`,
  camera guard so huge trees stay navigable.
- **Hallucinations?** Every answer is grounded in the built graph + README;
  citations are file paths + line numbers pulled from the graph, not the LLM.
