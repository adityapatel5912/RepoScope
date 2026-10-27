# TOON Compression Benchmark

This document records the empirical measurement of Token-Oriented Object Notation (TOON) serialization efficiency against compact JSON within RepoScope's context pack pipeline (`backend/context_compressor.py`).

RepoScope measures serialization performance across real open-source codebases under identical budget constraints. **No marketing claims (such as an unverified "85% token saving") are permitted.** Every number reported here was measured against compact JSON (`separators=(",", ":")`), using exact repository revisions.

---

## Benchmark Environment

- **Execution Date**: 2026-10-27T13:30:53Z
- **Operating System**: Windows 11 Pro (AMD64)
- **Python Version**: 3.14.6
- **`toon-format` Version**: 1.2.0
- **Context Pack Configuration**: `budget=8000`, `detail=skeleton`, `format=json` vs `format=toon`

---

## Methodology

1. **Repository Corpus**: Five prominent real-world repositories covering Python and TypeScript/JavaScript ecosystems:
   - `psf/requests` (Python)
   - `pallets/flask` (Python)
   - `encode/httpx` (Python)
   - `expressjs/express` (JavaScript)
   - `sindresorhus/got` (TypeScript / JavaScript)
2. **Deterministic Graph Extraction**: Each repository was parsed using RepoScope's tree-sitter parser suite to produce an AST graph (nodes, imports, calls, exports).
3. **Context Pack Generation**: `build_context_pack()` was executed for each repository at default settings (`budget=8000`, `detail=skeleton`).
4. **Serialization**:
   - **JSON**: Compact JSON via `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
   - **TOON**: Encoded via `toon_format.encode(payload, sort_keys=True)` after normalization.
5. **Measurement**:
   - **Byte Size**: UTF-8 encoded byte count of the serialized string.
   - **Token Count**: RepoScope's standard token estimator (`estimate_tokens()`).
   - **Roundtrip Integrity**: Decoded TOON (`toon_format.decode(text)`) compared against `json.loads(json.dumps(payload))` for deep structural equality.

---

## Corpus & Results

| Repository | Exact Commit | Commit Date | Graph (Nodes / Edges) | Included (Files / Symbols) | JSON (Bytes / Tokens) | TOON (Bytes / Tokens) | Byte Saving | Token Saving | Roundtrip |
|---|---|---|---|---|---|---|---|---|---|
| [`requests`](https://github.com/psf/requests) | `3c7baaa05ab4aa49cc819ce3a819d260de19c157` | 2026-10-26 | 937 / 1559 | 2 / 58 | 17,537 B / 7,855 | 12,846 B / 4,796 | +26.75% | **+38.94%** | PASS |
| [`flask`](https://github.com/pallets/flask) | `d086db856be187255b8ec61ef409357393020f32` | 2026-10-07 | 1858 / 2361 | 4 / 49 | 17,109 B / 7,696 | 12,685 B / 4,664 | +25.86% | **+39.40%** | PASS |
| [`httpx`](https://github.com/encode/httpx) | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` | 2026-02-23 | 1365 / 2059 | 5 / 59 | 17,584 B / 8,078 | 12,898 B / 4,931 | +26.65% | **+38.96%** | PASS |
| [`express`](https://github.com/expressjs/express) | `1c6f1b0fe4000977b9a7b4f34097e4d527dd9824` | 2026-10-23 | 341 / 162 | 50 / 35 | 14,836 B / 7,106 | 13,451 B / 4,702 | +9.34% | **+33.83%** | PASS |
| [`got`](https://github.com/sindresorhus/got) | `05b4476913da39a47dd8e20d29e250f28b0a6dca` | 2026-10-13 | 1602 / 2206 | 1 / 36 | 11,459 B / 5,332 | 8,126 B / 3,088 | +29.09% | **+42.09%** | PASS |

### Summary Statistics

- **Median Token Saving**: **+39.0%** (38.96%)
- **Median Byte Saving**: **+26.6%** (26.65%)
- **Token Saving Range**: +33.8% to +42.1%
- **Roundtrip Verification**: 5/5 passed (100% loss-free representation)

---

## Architectural Decision

1. **Default Serialization Remains JSON**:
   - Compact JSON (`format=json`, `application/json`) is universally supported by every LLM, client library, and API tooling without requiring external parser libraries.
   - Defaulting to JSON guarantees zero compatibility overhead and zero failure risk for consumers that do not explicitly opt into TOON.
2. **TOON Is Opt-In (`format=toon`)**:
   - For agents and consumers that support TOON parsing or wish to minimize context window consumption, TOON provides a verified ~39% token reduction.
   - TOON is packaged as an optional extra (`pip install reposcope[toon]`) and lazily imported.
   - Environment kill switch `REPOSCOPE_TOON=0` disables the serializer immediately across both REST and MCP interfaces.
3. **No 85% Claims**:
   - An 85% token saving claim circulating in early design notes was based on hypothetical uncompressed indentation vs TOON comparisons. Against compact JSON, the real measured savings are between 33% and 42% (median 39.0%).
   - All RepoScope documentation and marketing must cite the measured 39% median saving.

---

## Reproduction Runbook

To reproduce these benchmark results:

```powershell
# 1. Clone the benchmark corpus into a temp directory
$bench = Join-Path $env:TEMP "reposcope-toon-bench"
New-Item -ItemType Directory -Force $bench | Out-Null
git clone --depth 1 https://github.com/psf/requests.git "$bench\requests"
git clone --depth 1 https://github.com/pallets/flask.git "$bench\flask"
git clone --depth 1 https://github.com/encode/httpx.git "$bench\httpx"
git clone --depth 1 https://github.com/expressjs/express.git "$bench\express"
git clone --depth 1 https://github.com/sindresorhus/got.git "$bench\got"

# 2. Run the benchmark runner
python benchmarks/toon_benchmark.py `
  --repo "requests=$bench\requests" `
  --repo "flask=$bench\flask" `
  --repo "httpx=$bench\httpx" `
  --repo "express=$bench\express" `
  --repo "got=$bench\got" `
  --budget 8000 `
  --detail skeleton `
  --out "$bench\results.json"
```

---

## Limitations

- **Token Estimator**: The token counts are derived from RepoScope's character-and-whitespace heuristic estimator (`backend/context_compressor.py`). Token counts with specific tokenizer implementations (e.g. `cl100k_base`, `o200k_base`) will vary slightly but preserve the proportional advantage.
- **Payload Shape**: The benchmark evaluated AST skeleton context packs with symbol signatures and metadata. Packs containing full file bodies may exhibit different compression ratios depending on code commenting and syntax density.
- **Compact JSON Baseline**: All measurements compare against single-line compact JSON (`separators=(",", ":")`), not formatted or indented JSON. Comparing against pretty-printed JSON would artificially inflate savings figures.
