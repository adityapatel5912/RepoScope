import { useEffect, useState } from "react";
import { Cpu, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "./Toasts";

interface ProviderSpec {
  id: string;
  label: string;
  base_url: string;
  default_model: string;
  models: string[];
}

const DEFAULT_PROVIDERS: Record<string, ProviderSpec> = {
  groq: {
    id: "groq",
    label: "Groq",
    base_url: "https://api.groq.com/openai/v1",
    default_model: "llama-3.3-70b-versatile",
    models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"],
  },
  nvidia: {
    id: "nvidia",
    label: "NVIDIA NIM",
    base_url: "https://integrate.api.nvidia.com/v1",
    default_model: "meta/llama-3.3-70b-instruct",
    models: ["meta/llama-3.3-70b-instruct", "mistralai/mistral-large-2-instruct"],
  },
  openai: {
    id: "openai",
    label: "OpenAI",
    base_url: "https://api.openai.com/v1",
    default_model: "gpt-4o-mini",
    models: ["gpt-4o-mini", "gpt-4o"],
  },
  anthropic: {
    id: "anthropic",
    label: "Anthropic",
    base_url: "https://api.anthropic.com/v1",
    default_model: "claude-3-5-sonnet-latest",
    models: ["claude-3-5-sonnet-latest"],
  },
  custom: {
    id: "custom",
    label: "Custom OpenAI-compatible",
    base_url: "",
    default_model: "",
    models: [],
  },
};

export default function AIKeyPanel() {
  const [providers, setProviders] = useState<Record<string, ProviderSpec>>(DEFAULT_PROVIDERS);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [selectedProvider, setSelectedProvider] = useState("groq");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("llama-3.3-70b-versatile");
  const [baseUrl, setBaseUrl] = useState("");
  const [savedKeyLast4, setSavedKeyLast4] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load from sessionStorage on mount
  useEffect(() => {
    let isMounted = true;
    const p = sessionStorage.getItem("rs-ai-provider");
    const k = sessionStorage.getItem("rs-ai-key");
    const m = sessionStorage.getItem("rs-ai-model");
    const b = sessionStorage.getItem("rs-ai-base-url");

    if (k && isMounted) {
      setSavedKeyLast4(k.slice(-4));
      setStatus("saved");
      if (p) setSelectedProvider(p);
      if (m) setModel(m);
      if (b) setBaseUrl(b);
    }

    // Fetch providers from backend
    fetch("/api/ai/providers")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load AI providers");
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        if (data.providers) {
          setProviders(data.providers);
          const currentP = p || "groq";
          if (data.providers[currentP]) {
            if (!m) setModel(data.providers[currentP].default_model);
          }
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("AI providers fetch error:", err);
        setFetchError("Using offline provider list");
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleProviderChange = (newProvider: string) => {
    setSelectedProvider(newProvider);
    setStatus(savedKeyLast4 && newProvider === sessionStorage.getItem("rs-ai-provider") ? "saved" : "idle");
    setErrorMessage(null);
    const spec = providers[newProvider];
    if (spec) {
      setModel(spec.default_model);
      if (newProvider !== "custom") {
        setBaseUrl(spec.base_url);
      } else {
        setBaseUrl(sessionStorage.getItem("rs-ai-base-url") || "");
      }
    }
  };

  const validateKey = (prov: string, key: string, customUrl: string): boolean => {
    const trimmed = key.trim();
    if (!trimmed) return false;
    if (prov === "groq") {
      return trimmed.startsWith("gsk_") && trimmed.length >= 20;
    }
    if (prov === "nvidia") {
      return trimmed.startsWith("nvapi-") && trimmed.length >= 20;
    }
    if (prov === "openai") {
      return trimmed.startsWith("sk-") && trimmed.length >= 20;
    }
    if (prov === "anthropic") {
      return trimmed.startsWith("sk-ant-") && trimmed.length >= 20;
    }
    if (prov === "custom") {
      if (trimmed.length < 4) return false;
      if (customUrl && !/^https?:\/\//i.test(customUrl.trim())) return false;
      return true;
    }
    return trimmed.length >= 8;
  };

  const handleSave = () => {
    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      setStatus("error");
      setErrorMessage("API key cannot be empty");
      return;
    }

    if (!validateKey(selectedProvider, trimmedKey, baseUrl)) {
      setStatus("error");
      setErrorMessage("Invalid key");
      return;
    }

    // Save to sessionStorage only
    sessionStorage.setItem("rs-ai-provider", selectedProvider);
    sessionStorage.setItem("rs-ai-key", trimmedKey);
    sessionStorage.setItem("rs-ai-model", model.trim());
    if (selectedProvider === "custom" && baseUrl.trim()) {
      sessionStorage.setItem("rs-ai-base-url", baseUrl.trim());
    } else {
      sessionStorage.removeItem("rs-ai-base-url");
    }

    const last4 = trimmedKey.slice(-4);
    setSavedKeyLast4(last4);
    setApiKey(""); // clear plain text input
    setStatus("saved");
    setErrorMessage(null);
    toast.success("AI key saved (session only)");
  };

  const handleClear = () => {
    sessionStorage.removeItem("rs-ai-provider");
    sessionStorage.removeItem("rs-ai-key");
    sessionStorage.removeItem("rs-ai-model");
    sessionStorage.removeItem("rs-ai-base-url");

    setSavedKeyLast4(null);
    setApiKey("");
    setStatus("idle");
    setErrorMessage(null);
    toast.success("AI key cleared. Using server key.");
  };

  return (
    <section className="card p-4 flex flex-col gap-3 overflow-hidden min-w-0">
      {/* Header */}
      <div className="flex items-center gap-1.5">
        <Cpu size={12} className="text-text-muted" />
        <h3 className="label-caps">AI Provider (BYOK)</h3>
      </div>

      <p className="text-[11px] text-text-muted leading-relaxed">
        Stored in tab memory only — never persisted to the backend.
      </p>

      {/* Loading state */}
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-text-muted py-2">
          <RefreshCw size={12} className="animate-spin text-accent-cyan" />
          <span>Loading providers…</span>
        </div>
      ) : Object.keys(providers).length === 0 ? (
        /* Empty state */
        <div className="text-xs text-text-muted py-2" role="status">
          No AI providers available.
        </div>
      ) : (
        /* Body Form */
        <div className="flex flex-col gap-2.5">
          {fetchError && (
            <span className="text-[10px] text-amber-600 font-mono">
              Note: {fetchError}
            </span>
          )}

          {/* Provider dropdown */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-wider">
              Provider
            </label>
            <select
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="input !py-1.5 !px-2.5 !text-xs bg-bg-panel-alt cursor-pointer"
              aria-label="AI Provider"
            >
              {Object.values(providers).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {/* API Key input */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-wider">
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                setErrorMessage(null);
                if (status === "error") setStatus("idle");
              }}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
              placeholder={savedKeyLast4 ? `••••••••••••${savedKeyLast4}` : "Paste your API key…"}
              aria-label="API Key"
              className="input !py-1.5 font-mono !text-xs"
            />
          </div>

          {/* Model input */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-wider">
              Model
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. llama-3.3-70b-versatile"
              aria-label="AI Model"
              className="input !py-1.5 font-mono !text-xs"
            />
          </div>

          {/* Base URL (only shown when provider is custom) */}
          {selectedProvider === "custom" && (
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold uppercase text-text-muted tracking-wider">
                Base URL
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
                aria-label="Custom Base URL"
                className="input !py-1.5 font-mono !text-xs"
              />
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              className="btn-primary flex-1 !py-1.5 !px-3 !text-xs"
            >
              Save Key
            </button>
            {savedKeyLast4 && (
              <button
                onClick={handleClear}
                className="btn-secondary !py-1.5 !px-3 !text-xs shrink-0"
              >
                Clear Key
              </button>
            )}
          </div>

          {/* Status row beneath buttons */}
          <div className="pt-1 border-t border-border-hairline flex items-center justify-between min-w-0 overflow-hidden">
            {status === "error" ? (
              <div className="flex items-center gap-1.5 text-xs text-accent-rose min-w-0" role="alert">
                <span className="w-2 h-2 rounded-full bg-accent-rose shrink-0" />
                <AlertCircle size={11} className="shrink-0" />
                <span className="font-medium truncate" title={errorMessage || "Invalid key"}>{errorMessage || "Invalid key"}</span>
              </div>
            ) : savedKeyLast4 ? (
              <div className="flex items-center gap-1.5 text-xs text-text-primary min-w-0">
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                <CheckCircle2 size={11} className="text-emerald-500 shrink-0" />
                <span className="font-medium truncate" title={`Using your key • ending in ${savedKeyLast4}`}>
                  Using your key • ending in {savedKeyLast4}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-text-muted min-w-0">
                <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
                <span className="truncate">Using server key</span>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
