import React, { useState } from "react";
import type { CitationItem } from "../api/client";
import { CheckCircle2, AlertCircle, FileCode, CornerDownRight } from "lucide-react";

interface Props {
  citation: CitationItem;
  onCitationClick?: (citation: CitationItem) => void;
}

export default function CitationPill({ citation, onCitationClick }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onCitationClick?.(citation);
    window.dispatchEvent(
      new CustomEvent("reposcope:focus-node", {
        detail: {
          nodeId: citation.node_id,
          file: citation.path,
          line: citation.start_line,
        },
      }),
    );
  };

  const isVerified = Boolean(citation.verified);
  const lineLabel =
    citation.start_line != null
      ? citation.end_line != null && citation.end_line !== citation.start_line
        ? `:${citation.start_line}-${citation.end_line}`
        : `:${citation.start_line}`
      : "";

  const displayText = citation.symbol
    ? `${citation.symbol} (${citation.path}${lineLabel})`
    : `${citation.path}${lineLabel}`;

  return (
    <span
      className="relative inline-block my-0.5 mx-0.5 align-middle"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <button
        type="button"
        onClick={handleClick}
        data-testid="citation-pill"
        data-verified={isVerified}
        title={isVerified ? `Verified: ${citation.reason}` : `Unverified: ${citation.reason}`}
        className={`
          inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono transition-all duration-150 cursor-pointer
          ${
            isVerified
              ? "bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-900/50 hover:border-emerald-400"
              : "bg-amber-950/20 text-amber-300/80 border border-dashed border-amber-600/40 hover:bg-amber-900/30 hover:border-amber-500"
          }
        `}
      >
        {isVerified ? (
          citation.reason === "snapped" ? (
            <CornerDownRight size={12} className="text-emerald-400 shrink-0" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={12} className="text-emerald-400 shrink-0" aria-hidden="true" />
          )
        ) : (
          <AlertCircle size={12} className="text-amber-400 shrink-0" aria-hidden="true" />
        )}
        <span className="truncate max-w-[280px]">{displayText}</span>
        {!isVerified && (
          <span className="text-[10px] text-amber-400/70 font-sans uppercase tracking-wider ml-0.5">
            unverified
          </span>
        )}
      </button>

      {/* Hover preview tooltip using spans with block styling to avoid validateDOMNesting warning in <p> */}
      {showTooltip && (
        <span
          data-testid="citation-hover-preview"
          className="
            absolute bottom-full left-0 mb-1.5 z-50 w-80 max-w-sm p-2.5 rounded-lg block
            bg-bg-panel border border-border-default shadow-xl text-xs text-text-primary
            pointer-events-none transition-opacity duration-150
          "
        >
          <span className="flex items-center justify-between gap-2 pb-1.5 mb-1.5 border-b border-border-subtle">
            <span className="flex items-center gap-1.5 truncate">
              <FileCode size={13} className="text-accent-cyan shrink-0" />
              <span className="font-mono font-semibold truncate text-text-primary">
                {citation.path}
                {lineLabel}
              </span>
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded uppercase font-semibold shrink-0 ${
                isVerified
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "bg-amber-500/20 text-amber-300"
              }`}
            >
              {isVerified ? `${Math.round(citation.confidence * 100)}% verified` : "unverified"}
            </span>
          </span>

          <span className="space-y-1 mb-2 text-text-secondary text-[11px] block">
            {citation.symbol && (
              <span className="block">
                <span className="text-text-muted">Symbol: </span>
                <span className="font-mono text-accent-emerald">{citation.symbol}</span>
              </span>
            )}
            {citation.node_id && (
              <span className="block">
                <span className="text-text-muted">Node: </span>
                <span className="font-mono text-text-secondary">{citation.node_id}</span>
              </span>
            )}
            <span className="block">
              <span className="text-text-muted">Reason: </span>
              <span className="capitalize">{citation.reason}</span>
            </span>
          </span>

          {citation.preview ? (
            <span className="block p-2 rounded bg-bg-base/80 border border-border-subtle text-[11px] font-mono text-text-muted overflow-x-auto max-h-36 whitespace-pre">
              {citation.preview}
            </span>
          ) : (
            <span className="block text-text-muted italic text-[11px]">
              {isVerified ? "No preview available" : `Cannot preview: ${citation.reason}`}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
