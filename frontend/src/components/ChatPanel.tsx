import { createContext, useContext, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { streamChat } from "../api/client";
import type { ContextPayload } from "../api/client";
import { toast } from "./Toasts";
import { Send, Copy, Check, Mic, MicOff, User } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  text: string;
  ts: number;
  done?: boolean;
}

interface DebugEvent {
  ts: string;
  event: string;
  summary: string;
}

interface Props {
  mode: string;
  repo: string | null;
  disabled?: boolean;
  onContext: (d: ContextPayload) => void;
  onTracking: (d: unknown) => void;
  onToken: () => void;
  onEvent: (e: string) => void;
  debugMode: boolean;
  prefillMessage?: string;
  onPrefillConsumed?: () => void;
}

// FILE 2 — six example prompts for the empty state (2×3 grid)
const EXAMPLE_PROMPTS = [
  "Give me a full overview of this repo",
  "How do I set up and run this project locally?",
  "Explain the overall architecture and data flow",
  "What are the most important files to understand first?",
  "Are there any open issues or known bugs?",
  "How is testing set up?",
];

// `path/to/file.ts:42` → citation chip (suppressed inside table cells)
const CITATION_RE = /^[\w./@-]+\.[A-Za-z0-9]+(:\d+)?$/;
const InTableContext = createContext(false);

// Proper named component so useContext hook is valid
function InlineCode({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
  const inTable = useContext(InTableContext);
  const text = String(children ?? "").replace(/\n$/, "");
  if (!inTable && CITATION_RE.test(text)) {
    return <span className="citation-chip">{text}</span>;
  }
  return <code className={className} {...props}>{children}</code>;
}

// ── Web Speech (mic) — optional capability ───────────────────────────────────
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
type SpeechCtor = new () => SpeechRecognitionLike;

function getSpeechCtor(): SpeechCtor | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition) as SpeechCtor | null ?? null;
}

// ── Dark code block with copy button (FILE 2) ────────────────────────────────
function CodeBlock({ className, children }: { className?: string; children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className ?? "");
  let lang = (match?.[1] ?? "").toLowerCase();
  const code = String(children ?? "").replace(/\n$/, "");

  // Normalize shell/bash aliases so syntax highlighting works
  if (["sh", "shell", "zsh", "terminal", "console"].includes(lang)) {
    lang = "bash";
  } else if (["cmd", "ps1", "pwsh"].includes(lang)) {
    lang = "powershell";
  }

  // If no language was specified, auto-detect bash commands or multiline
  if (!lang) {
    if (
      code.includes("\n") ||
      /^(\$|\b(npm|npx|yarn|pnpm|pip|python|python3|cd|git|curl|uvicorn|cat|node|docker|mkdir|ls|cp|mv|chmod|export)\b)/m.test(code)
    ) {
      lang = "bash";
    } else {
      lang = "text";
    }
  }

  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="code-block-wrapper relative group my-2.5 rounded-lg overflow-hidden border-[1.5px] border-[#2E2A24] bg-[#1E1B16] shadow-sm">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#141210] border-b border-[#2E2A24]">
        <span className="text-[10px] font-mono text-[#D4CEBF] font-semibold uppercase tracking-wider">{lang}</span>
        <button
          onClick={copy}
          aria-label="Copy code"
          className="flex items-center gap-1 text-[10px] font-medium text-[#D4CEBF] hover:text-white transition-colors"
        >
          {copied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
          <span className={copied ? "text-emerald-400 font-semibold" : ""}>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <div className="code-block-content overflow-x-auto">
        <SyntaxHighlighter
          style={oneDark}
          language={lang === "text" ? undefined : lang}
          PreTag="div"
          customStyle={{
            margin: 0,
            padding: "12px 16px",
            background: "#1E1B16",
            fontSize: "12px",
            fontFamily: '"JetBrains Mono", monospace',
            lineHeight: "1.6",
            color: "#F5F1E8",
          }}
          codeTagProps={{
            style: {
              fontFamily: '"JetBrains Mono", monospace',
              background: "transparent",
              color: "#F5F1E8",
              whiteSpace: "pre",
            },
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

// ── Hover copy button for assistant messages ────────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={copy}
      aria-label="Copy message"
      className="
        opacity-0 group-hover:opacity-100 focus-visible:opacity-100
        absolute top-2 right-2
        flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold
        bg-bg-panel border border-border-subtle shadow-sm
        text-text-secondary hover:text-text-primary
        transition-all duration-150
      "
    >
      {copied ? <Check size={10} className="text-accent-emerald" /> : <Copy size={10} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ── Empty state (FILE 2): centered heading + TRY ASKING + 2×3 prompt grid ──
function EmptyChat({ repoName, onPick }: { repoName: string; onPick: (p: string) => void }) {
  return (
    <div className="flex-1 w-full flex flex-col items-center justify-start my-auto px-4 sm:px-6 py-3 sm:py-6 gap-3 sm:gap-4 overflow-y-auto">
      <div className="text-center max-w-lg shrink-0">
        <h2 className="text-base sm:text-lg font-bold text-text-primary">
          Ask anything about <span className="text-accent-cyan truncate inline-block max-w-[200px] align-bottom" title={repoName}>{repoName}</span>
        </h2>
        <p className="text-xs text-text-muted mt-1 leading-relaxed">
          Architecture, implementation, setup, and file-level questions all work here.
        </p>
      </div>

      <div className="w-full max-w-xl shrink-0">
        <p className="label-caps text-center mb-2 !text-[10px]">Try asking</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-2.5">
          {EXAMPLE_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => onPick(p)}
              className="
                text-left text-xs font-medium text-text-secondary leading-snug
                bg-bg-panel border-[1.5px] border-border-subtle rounded-lg shadow-sm
                px-3 py-2 sm:px-3.5 sm:py-2.5
                hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none
                active:translate-x-[2px] active:translate-y-[2px]
                transition-all duration-100
              "
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({
  mode, repo, disabled, onContext, onTracking, onToken, onEvent,
  debugMode, prefillMessage, onPrefillConsumed,
}: Props) {
  const [msgs, setMsgs]         = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [busy, setBusy]         = useState(false);
  const [listening, setListening] = useState(false);
  const [debugLog, setDebugLog] = useState<DebugEvent[]>([]);
  const bottomRef               = useRef<HTMLDivElement>(null);
  const inputRef                = useRef<HTMLTextAreaElement>(null);
  const controllerRef           = useRef<AbortController | null>(null);
  const recogRef                = useRef<SpeechRecognitionLike | null>(null);

  const addDebug = (event: string, summary: string) => {
    const ts = new Date().toLocaleTimeString();
    setDebugLog((d) => [...d.slice(-19), { ts, event, summary }]);
  };

  // Auto-scroll on new tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  // Handle pre-fill from node drawer / example cards
  useEffect(() => {
    if (prefillMessage) {
      setInput(prefillMessage);
      onPrefillConsumed?.();
      inputRef.current?.focus();
    }
  }, [prefillMessage, onPrefillConsumed]);

  // Abort any in-flight stream when the panel unmounts
  useEffect(() => () => controllerRef.current?.abort(), []);

  const send = async (raw?: string) => {
    const q = (raw ?? input).trim();
    if (!q || busy || disabled) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setMsgs((m) => [...m, { role: "user", text: q, ts: Date.now() }, { role: "assistant", text: "", ts: Date.now(), done: false }]);
    setBusy(true);

    // Cancel any previous stream before starting a new one
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await streamChat(mode, q, repo, {
        onContext: (ctx) => {
          onContext(ctx);
          addDebug("context", `${ctx.node_count} nodes, ${ctx.edge_count} edges`);
          onEvent("context");
        },
        onToken: (t) => {
          setMsgs((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, text: last.text + t };
            return copy;
          });
          onToken();
          onEvent("token");
        },
        onTracking: (d) => {
          onTracking(d);
          addDebug("tracking", "tracking data received");
          onEvent("tracking");
        },
        onDone: () => {
          setMsgs((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], done: true };
            return copy;
          });
          setBusy(false);
          addDebug("done", "stream complete");
          onEvent("done");
        },
        onError: (msg) => {
          setMsgs((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], text: `⚠️ ${msg}`, done: true };
            return copy;
          });
          setBusy(false);
          toast.error(msg);
          addDebug("error", msg);
          onEvent("error");
        },
      }, { signal: controller.signal });
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setBusy(false);
        return;
      }
      const msg = e instanceof Error ? e.message : "Stream failed";
      toast.error(msg);
      setBusy(false);
    }
  };

  // ── Mic (Web Speech API) ──
  const toggleMic = () => {
    if (listening) {
      recogRef.current?.stop();
      return;
    }
    const Ctor = getSpeechCtor();
    if (!Ctor) {
      toast.error("Voice input is not supported in this browser");
      return;
    }
    const recog = new Ctor();
    recog.lang = "en-US";
    recog.interimResults = false;
    recog.continuous = false;
    recog.onresult = (e) => {
      const transcript = Array.from({ length: e.results.length }, (_, i) => e.results[i][0].transcript).join(" ").trim();
      if (transcript) setInput((v) => (v ? `${v} ${transcript}` : transcript));
    };
    recog.onend = () => setListening(false);
    recog.onerror = () => { setListening(false); toast.error("Voice input failed"); };
    recogRef.current = recog;
    setListening(true);
    recog.start();
  };

  // Cleanup mic on unmount
  useEffect(() => () => recogRef.current?.stop(), []);

  const placeholder =
    mode === "tracking"  ? "Say 'what changed?' or 'check the repo'" :
    mode === "incident"  ? "Describe the incident or paste an alert…" :
                           "Ask about the repo — 'How does auth work?'";

  // Auto-resize textarea up to ~5 lines
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 110) + "px";
  };

  const repoName = repo?.split("/")[1] ?? "this repo";

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* ── Messages ── */}
      <div
        role="log"
        aria-live="polite"
        className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4"
      >
        {msgs.length === 0 && (
          disabled
            ? <div className="flex-1 flex items-center justify-center">
                <p className="text-sm text-text-muted text-center px-6">
                  Load a repository to start chatting.
                </p>
              </div>
            : <EmptyChat repoName={repoName} onPick={(p) => { setInput(p); inputRef.current?.focus(); }} />
        )}

        {msgs.map((m, i) => (
          <div
            key={i}
            className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {m.role === "user" ? (
              <>
                <span className="hidden sm:flex w-6 h-6 rounded-md bg-bg-panel-alt border border-border-subtle items-center justify-center shrink-0 mt-0.5 order-2">
                  <User size={12} className="text-text-muted" />
                </span>
                <div className="
                  order-1 max-w-[85%] sm:max-w-[80%] px-4 py-2.5
                  bg-bg-panel border-[1.5px] border-border-subtle shadow-sm rounded-lg
                  text-sm text-text-primary whitespace-pre-wrap break-words
                ">
                  {m.text}
                </div>
              </>
            ) : (
              <div className="flex gap-2.5 max-w-[95%] sm:max-w-[90%] min-w-0">
                {/* Avatar mark — RepoScope logo icon */}
                <img
                  src="/icon.png"
                  alt=""
                  className="w-6 h-6 rounded-md object-cover border border-border-subtle shrink-0 mt-5"
                  aria-hidden="true"
                />
                <div className="relative group min-w-0 flex-1">
                  {/* Header: RepoScope + timestamp */}
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-text-primary">RepoScope</span>
                    <span className="text-[11px] text-text-muted">
                      {new Date(m.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <div className="
                    px-4 py-3 bg-bg-panel-alt
                    border-[1.5px] border-border-subtle shadow-sm rounded-lg
                    break-words overflow-hidden
                  ">
                    {m.text ? (
                      <div className="md-body">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code: ({ className, children, ...props }) => {
                              // fenced code block or multiline code → CodeBlock; inline single-line → InlineCode
                              const isBlock = Boolean(className) || String(children ?? "").includes("\n");
                              if (isBlock) return <CodeBlock className={className}>{children}</CodeBlock>;
                              return <InlineCode className={className} {...props}>{children}</InlineCode>;
                            },
                            pre: ({ children }) => <>{children}</>,
                            table: ({ children }) => (
                              <div className="md-table-wrap">
                                <table>{children}</table>
                              </div>
                            ),
                            td: ({ children, ...props }) => (
                              <InTableContext.Provider value={true}>
                                <td {...props}>{children}</td>
                              </InTableContext.Provider>
                            ),
                            th: ({ children, ...props }) => (
                              <InTableContext.Provider value={true}>
                                <th {...props}>{children}</th>
                              </InTableContext.Provider>
                            ),
                          }}
                        >
                          {m.text}
                        </ReactMarkdown>
                      </div>
                    ) : busy && i === msgs.length - 1 ? (
                      <span className="flex gap-1.5 items-center py-1">
                        <span className="dot-pulse" />
                        <span className="dot-pulse" />
                        <span className="dot-pulse" />
                      </span>
                    ) : null}
                  </div>
                  {m.done && m.text && <CopyBtn text={m.text} />}
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Debug panel ── */}
      {debugMode && (
        <div className="
          shrink-0 max-h-36 overflow-y-auto
          border-t border-border-hairline
          bg-bg-panel-alt px-3 py-2
          font-mono text-[11px]
        ">
          <div className="text-accent-amber font-semibold mb-1">
            Debug — {debugLog.length} events
          </div>
          {debugLog.length === 0 && (
            <span className="text-text-muted">No events yet.</span>
          )}
          {[...debugLog].reverse().map((e, i) => (
            <div key={i} className="flex gap-2 py-0.5 items-baseline">
              <span className="text-text-muted shrink-0">{e.ts}</span>
              <span className={`shrink-0 font-semibold w-16 ${
                e.event === "context"  ? "text-accent-cyan"    :
                e.event === "token"    ? "text-accent-emerald" :
                e.event === "tracking" ? "text-accent-amber"   :
                e.event === "done"     ? "text-text-muted"     :
                e.event === "error"    ? "text-accent-rose"    :
                                         "text-text-muted"
              }`}>{e.event}</span>
              <span className="text-text-muted break-all">{e.summary}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Input bar ── */}
      <div className="shrink-0 px-3 pb-3 pt-2 border-t border-border-hairline">
        <div className="flex items-end gap-2">
          {/* Mic — ghost circle on the left */}
          <button
            onClick={toggleMic}
            title={listening ? "Stop voice input" : "Voice input"}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            aria-pressed={listening}
            className={`
              shrink-0 w-9 h-9 rounded-full flex items-center justify-center
              border-[1.5px] border-border-subtle transition-colors
              ${listening
                ? "bg-accent-cyan text-white animate-pulse"
                : "bg-bg-panel text-text-muted hover:text-text-primary hover:bg-bg-panel-alt"}
            `}
          >
            {listening ? <MicOff size={15} /> : <Mic size={15} />}
          </button>

          <div className="
            flex-1 flex items-end gap-2 min-w-0
            bg-bg-panel border-[1.5px] border-border-subtle
            rounded-lg px-3 py-2
            focus-within:shadow-[0_0_0_3px_rgba(240,80,60,0.25)]
            transition-shadow duration-150
          ">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInput}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder={disabled ? "Load a repo first…" : placeholder}
              disabled={busy || disabled}
              rows={1}
              aria-label="Chat input"
              className="
              flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted
              resize-none outline-none focus-visible:outline-none leading-relaxed
              disabled:opacity-50
              min-h-[24px] max-h-[110px]
            "
              style={{ height: "24px" }}
            />
          </div>

          <button
            onClick={() => void send()}
            disabled={busy || disabled || !input.trim()}
            aria-label="Send message"
            className="
              shrink-0 w-9 h-9 flex items-center justify-center rounded-lg
              bg-accent-cyan text-white border-[1.5px] border-border-subtle shadow-sm
              hover:bg-accent-hover hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none
              disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-x-0
              transition-all duration-100
            "
          >
            {busy ? <span className="btn-spinner" /> : <Send size={15} />}
          </button>
        </div>
        <p className="text-[10px] text-text-muted mt-1.5 px-1">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
