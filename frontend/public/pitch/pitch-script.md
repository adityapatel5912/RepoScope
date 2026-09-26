# RepoScope — 3-Minute Demo Script

**(0:00–0:20) Hook**
Every developer knows this moment: you join a project, and the codebase is a
maze. You open an IDE to read, a browser to search, an AI chatbot to ask —
and the chatbot guesses. It invents function names, cites files that don't
exist, and sounds confident doing it. Nothing cites its sources, so nothing
is trustworthy.

**(0:20–0:40) The pitch**
RepoScope turns any GitHub repository into an interactive architecture graph,
answers questions about it in plain English with citations, and tracks what
changes over time. One workspace replaces five tools, and every answer comes
with a receipt: the exact file, function, and line number it came from.
Trust is the feature.

**(0:40–1:10) Live demo, part one — See**
I paste a GitHub URL. In seconds, RepoScope builds a layered architecture
graph — client, backend, storage, external integrations, compute — laid out
automatically with right-angle edges and a legend. This is the repo of our
other hackathon project, Verdict: one hundred fifty-four files, mapped and
grouped by layer. Zoom out for the shape of the system; zoom in for a single
function.

**(1:10–1:50) Live demo, part two — Ask**
Now I ask: "Give me a full overview of this repo." The answer streams in with
a bold one-line summary, a table of the key files, and citations like
`backend/main.py` — clickable, verifiable, never hallucinated. Ask about any
function and it explains the real code, because every answer is grounded in a
knowledge graph built from the actual repository — not from the model's
imagination.

**(1:50–2:20) Live demo, part three — Tour and Impact**
Code Tours walk a new teammate through any module step by step — the graph
pans to each file, numbered badges marking progress, a plain-English
explanation under each stop. And before you change a function, What-If
Impact Analysis shows the blast radius: direct callers, transitive callers,
a risk score, and suggested tests, so you know exactly what your change can
break before you break it.

**(2:20–2:40) Track and ship**
Switch to Track mode and RepoScope reports new commits, pull requests, and
issues on demand — your repo's pulse in one place, grouped by change type
with breaking changes flagged first. And when it's time to rebuild the whole
project with an AI agent, the Reverse Build Prompt turns any repository into
a ready-to-paste agent brief in one click.

**(2:40–3:00) Close**
RepoScope was built for the IBM Bob 2.0 Hackathon — Bob drove most of the
build across eight guided sessions, with Z Code pairing on the complex
diagnostics. It's open source, it runs on free-tier LLM keys with automatic
rate-limit rotation, and it works on any public repo today. Try it with your
own project. RepoScope. See your repo. Understand it. Track it.
