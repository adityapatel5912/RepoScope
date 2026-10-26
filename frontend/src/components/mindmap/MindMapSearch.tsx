/**
 * MindMapSearch.tsx
 * Debounced search input for the mind map.
 * Matches label and path, announces results via an accessible live region,
 * and clears on Escape.
 */

import React, { useState, useEffect, useRef } from "react";
import { Search, X, ChevronUp, ChevronDown } from "lucide-react";

export interface MindMapSearchProps {
  query: string;
  onQueryChange: (q: string) => void;
  matchCount: number;
  currentMatchIndex?: number;
  onNextMatch?: () => void;
  onPrevMatch?: () => void;
  onClose?: () => void;
}

export const MindMapSearch: React.FC<MindMapSearchProps> = ({
  query,
  onQueryChange,
  matchCount,
  currentMatchIndex = 0,
  onNextMatch,
  onPrevMatch,
  onClose,
}) => {
  const [internalVal, setInternalVal] = useState(query);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync internal state when external query changes
  useEffect(() => {
    setInternalVal(query);
  }, [query]);

  // Debounce input to parent query change
  useEffect(() => {
    const timer = setTimeout(() => {
      if (internalVal !== query) {
        onQueryChange(internalVal);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [internalVal, query, onQueryChange]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setInternalVal("");
      onQueryChange("");
      onClose?.();
      inputRef.current?.blur();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) {
        onPrevMatch?.();
      } else {
        onNextMatch?.();
      }
    }
  };

  const handleClear = () => {
    setInternalVal("");
    onQueryChange("");
    onClose?.();
    inputRef.current?.focus();
  };

  const announcement = internalVal.trim()
    ? matchCount === 0
      ? `No matches found for ${internalVal}`
      : `${matchCount} match${matchCount === 1 ? "" : "es"} found for ${internalVal}`
    : "";

  return (
    <div className="relative flex items-center min-w-[200px] max-w-[280px]">
      <label htmlFor="mindmap-search-input" className="sr-only">
        Search mind map
      </label>
      <Search
        size={14}
        className="absolute left-2.5 text-text-muted pointer-events-none"
      />
      <input
        ref={inputRef}
        id="mindmap-search-input"
        type="text"
        role="searchbox"
        placeholder="Search files & symbols..."
        value={internalVal}
        onChange={(e) => setInternalVal(e.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Search mind map by name or path"
        className="
          w-full pl-8 pr-16 py-1 text-xs font-mono rounded-md
          bg-bg-panel border-[1.5px] border-border-subtle shadow-sm
          focus:outline-none focus:ring-2 focus:ring-accent-cyan
          placeholder:text-text-muted
        "
      />

      {/* Accessible live status for screen readers */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      {/* Right controls: match count and navigation */}
      <div className="absolute right-1.5 flex items-center gap-1">
        {internalVal && (
          <span
            data-testid="search-match-count"
            className="text-[10px] font-mono text-text-muted px-1"
          >
            {matchCount > 0
              ? `${currentMatchIndex + 1}/${matchCount}`
              : "0"}
          </span>
        )}
        {matchCount > 1 && (
          <div className="flex items-center">
            <button
              type="button"
              onClick={onPrevMatch}
              aria-label="Previous match"
              title="Previous match (Shift+Enter)"
              className="p-0.5 text-text-muted hover:text-text-primary rounded"
            >
              <ChevronUp size={12} />
            </button>
            <button
              type="button"
              onClick={onNextMatch}
              aria-label="Next match"
              title="Next match (Enter)"
              className="p-0.5 text-text-muted hover:text-text-primary rounded"
            >
              <ChevronDown size={12} />
            </button>
          </div>
        )}
        {internalVal && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear search"
            className="p-0.5 text-text-muted hover:text-text-primary rounded"
          >
            <X size={12} />
          </button>
        )}
      </div>
    </div>
  );
};
