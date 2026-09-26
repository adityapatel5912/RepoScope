import { useRef, useState, useCallback } from "react";
import { loadRepo } from "../api/client";

const LOAD_STEPS = [
  "Cloning repository",
  "Indexing files",
  "Building code graph",
  "Ready",
];

export interface RepoLoadResult {
  owner: string;
  repo: string;
  file_count?: number;
  node_count?: number;
  edge_count?: number;
  readme_length?: number;
}

/**
 * Owns the repo-load flow: URL validation, staged progress, race-guarded
 * requests. Used by the TopBar input; results bubble up via onLoaded.
 */
export function useRepoLoader(onLoaded: (info: RepoLoadResult) => void) {
  const [url, setUrl]         = useState("");
  const [loading, setLoading] = useState(false);
  const [stepIdx, setStepIdx] = useState(-1);
  const [urlError, setUrlError] = useState<string | null>(null);
  const loadIdRef             = useRef(0);
  const lastUrlRef            = useRef("");

  const steps = LOAD_STEPS.map((label, i) => ({
    label,
    done: stepIdx > i,
    active: stepIdx === i,
  }));

  const submit = useCallback(async (raw?: string) => {
    const trimmed = (raw ?? url).trim();
    if (!trimmed || loading) return;
    // Validate GitHub URL shape before hitting the backend
    if (!/^(https?:\/\/)?github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(trimmed)) {
      setUrlError("Enter a valid GitHub repo URL, e.g. github.com/owner/repo");
      return;
    }
    setUrlError(null);
    const id = ++loadIdRef.current;
    lastUrlRef.current = trimmed;
    setLoading(true);
    setStepIdx(0);

    const advance = (i: number) => new Promise<void>((r) => {
      setTimeout(() => { setStepIdx(i); r(); }, 400);
    });

    try {
      await advance(1);
      const result = await loadRepo(trimmed);
      if (id !== loadIdRef.current) return;  // stale — a newer load started
      await advance(2);
      await advance(3);
      onLoaded(result);
      setStepIdx(4);
    } catch (e: unknown) {
      if (id !== loadIdRef.current) return;  // stale
      const msg = e instanceof Error ? e.message : String(e);
      setUrlError(`Failed to load repo: ${msg}`);
      setStepIdx(-1);
    } finally {
      if (id === loadIdRef.current) setLoading(false);
    }
  }, [url, loading, onLoaded]);

  return {
    url, setUrl,
    loading, steps, stepIdx,
    urlError, setUrlError,
    submit,
    resubmit: () => void submit(lastUrlRef.current),
    hasLastUrl: () => Boolean(lastUrlRef.current),
  };
}

export type RepoLoader = ReturnType<typeof useRepoLoader>;
