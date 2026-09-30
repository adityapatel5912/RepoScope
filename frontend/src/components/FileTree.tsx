/**
 * FileTree.tsx
 * Sidebar card listing every analyzed file of the loaded repo, in the
 * GitIngest tree format (│ ├ └ characters, monospace alignment — FILE 4).
 * Collapsible directories, search filter, per-file download.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { downloadRepoFile } from "../api/features";
import { toast } from "./Toasts";
import { FolderTree, Search, Download, ChevronDown, ChevronRight, FileCode2, Loader2 } from "lucide-react";

interface RawNode {
  id: string;
  type: string;
  label: string;
}

interface DirNode {
  kind: "dir";
  name: string;
  path: string;
  children: TreeNode[];
}
interface FileNode {
  kind: "file";
  name: string;
  path: string;
}
type TreeNode = DirNode | FileNode;

interface Props {
  rawNodes: unknown[];
  /** Render without the outer card chrome (for embedding inside modals). */
  embedded?: boolean;
  /** Card title override (default "File Tree"). */
  title?: string;
  /** Currently highlighted file path (works with onSelectFile). */
  selectedPath?: string | null;
  /** Makes file rows clickable and reports the clicked path. */
  onSelectFile?: (path: string) => void;
  /** Overrides the default API download (e.g. scaffold files from memory). */
  onDownloadFile?: (path: string) => Promise<void>;
  /** Hides the per-row download buttons entirely. */
  hideDownload?: boolean;
}

// ── Build a nested tree from flat file paths ────────────────────────────────
function buildTree(files: FileNode[]): DirNode {
  const root: DirNode = { kind: "dir", name: "", path: "", children: [] };
  const dirIndex = new Map<string, DirNode>([["", root]]);

  const ensureDir = (path: string): DirNode => {
    const existing = dirIndex.get(path);
    if (existing) return existing;
    const cut = path.lastIndexOf("/");
    const parentPath = cut === -1 ? "" : path.slice(0, cut);
    const name = cut === -1 ? path : path.slice(cut + 1);
    const parent = ensureDir(parentPath);
    const dir: DirNode = { kind: "dir", name, path, children: [] };
    dirIndex.set(path, dir);
    parent.children.push(dir);
    return dir;
  };

  for (const f of files) {
    const cut = f.path.lastIndexOf("/");
    const parent = ensureDir(cut === -1 ? "" : f.path.slice(0, cut));
    parent.children.push(f);
  }

  const sortRec = (d: DirNode) => {
    d.children.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    d.children.forEach((c) => { if (c.kind === "dir") sortRec(c); });
  };
  sortRec(root);
  return root;
}

// ── One row (file or directory), with FILE 4 box-drawing prefix ─────────────
function Row({
  node, prefix, isLast, depth, expanded, onToggleDir, onDownload, downloading,
  onSelectFile, selectedPath, hideDownload,
}: {
  node: TreeNode;
  prefix: string;
  isLast: boolean;
  depth: number;
  expanded: Set<string>;
  onToggleDir: (path: string) => void;
  onDownload: (path: string) => void;
  downloading: string | null;
  onSelectFile?: (path: string) => void;
  selectedPath?: string | null;
  hideDownload?: boolean;
}) {
  const tee = isLast ? "└─ " : "├─ ";
  const childPrefix = prefix + (isLast ? "   " : "│  ");
  const isOpen = expanded.has(node.path);

  if (node.kind === "dir") {
    return (
      <>
        <button
          onClick={() => onToggleDir(node.path)}
          className="w-full min-w-0 flex items-center gap-1 text-left group hover:bg-bg-panel-alt rounded-sm overflow-hidden"
          style={{ paddingLeft: 0 }}
          aria-expanded={isOpen}
          title={node.path}
        >
          <span className="font-mono text-[10.5px] text-border-strong shrink-0 select-none">
            {prefix}{tee}
          </span>
          <span className="shrink-0 text-text-muted">
            {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </span>
          <span className="font-mono text-[11px] font-semibold text-text-primary truncate min-w-0 group-hover:text-accent-hover">
            {node.name}/
          </span>
        </button>
        {isOpen && node.children.map((child, i) => (
          <Row
            key={child.path}
            node={child}
            prefix={childPrefix}
            isLast={i === node.children.length - 1}
            depth={depth + 1}
            expanded={expanded}
            onToggleDir={onToggleDir}
            onDownload={onDownload}
            downloading={downloading}
            onSelectFile={onSelectFile}
            selectedPath={selectedPath}
            hideDownload={hideDownload}
          />
        ))}
      </>
    );
  }

  const isSelected = selectedPath != null && node.path === selectedPath;
  const clickable = onSelectFile != null;

  const fileRow = (
    <>
      <span className="font-mono text-[10.5px] text-border-strong shrink-0 select-none">
        {prefix}{tee}
      </span>
      <FileCode2 size={11} className={`shrink-0 ${isSelected ? "text-accent-cyan" : "text-text-muted"}`} />
      <span className={`font-mono text-[11px] truncate min-w-0 flex-1 ${isSelected ? "text-accent-cyan font-semibold" : "text-text-secondary"}`} title={node.path}>
        {node.name}
      </span>
      {!hideDownload && (
        <button
          onClick={(e) => { e.stopPropagation(); onDownload(node.path); }}
          disabled={downloading != null}
          aria-label={`Download ${node.name}`}
          title={`Download ${node.name}`}
          className="shrink-0 w-5 h-5 flex items-center justify-center rounded
            text-text-muted hover:text-accent-hover hover:bg-bg-panel-hover
            disabled:opacity-40 transition-colors"
        >
          {downloading === node.path ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
        </button>
      )}
    </>
  );

  if (clickable) {
    return (
      <button
        onClick={() => onSelectFile(node.path)}
        className={`w-full min-w-0 flex items-center gap-1 text-left rounded-sm transition-colors overflow-hidden
          ${isSelected ? "bg-accent-cyan/10" : "hover:bg-bg-panel-alt"}`}
      >
        {fileRow}
      </button>
    );
  }

  return (
    <div className="w-full min-w-0 flex items-center gap-1 group hover:bg-bg-panel-alt rounded-sm overflow-hidden">
      {fileRow}
    </div>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────
export default function FileTree({
  rawNodes, embedded = false, title, selectedPath = null, onSelectFile,
  onDownloadFile, hideDownload = false,
}: Props) {
  const [query, setQuery]       = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState<string | null>(null);

  const doDownload = async (path: string) => {
    if (downloading) return;
    setDownloading(path);
    try {
      if (onDownloadFile) await onDownloadFile(path);
      else await downloadRepoFile(path);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  };

  const files: FileNode[] = useMemo(
    () =>
      (rawNodes as RawNode[])
        .filter((n) => n?.type === "file" && n.label)
        .map((n) => ({ kind: "file" as const, name: n.label.split("/").pop() ?? n.label, path: String(n.label) })),
    [rawNodes],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => f.path.toLowerCase().includes(q));
  }, [files, query]);

  const tree = useMemo(() => buildTree(filtered), [filtered]);

  // Auto-expand everything while searching
  const effectiveExpanded = useMemo(() => {
    if (!query.trim()) return expanded;
    const all = new Set<string>();
    const walk = (d: DirNode) => {
      all.add(d.path);
      d.children.forEach((c) => { if (c.kind === "dir") walk(c); });
    };
    walk(tree);
    return all;
  }, [tree, expanded, query]);

  const toggleDir = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  };

  // Expand top-level dirs by default on first load
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current || files.length === 0) return;
    seeded.current = true;
    setExpanded((prev) => {
      const next = new Set(prev);
      tree.children.forEach((c) => { if (c.kind === "dir") next.add(c.path); });
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files.length]);

  const body = (
    <>
      <div className={`flex items-center gap-1.5 ${embedded ? "mb-1.5" : ""}`}>
        <FolderTree size={12} className="text-text-muted" />
        <h3 className="label-caps">{title ?? "File Tree"}</h3>
        <span className="ml-auto text-[10px] font-mono text-text-muted">{files.length}</span>
      </div>

      <div className="relative">
        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter files…"
          aria-label="Filter files"
          className="input !py-1.5 !pl-7 !text-xs font-mono"
        />
      </div>

      <div className="overflow-y-auto overflow-x-hidden max-h-64 -mx-1 px-1">
        {files.length === 0 ? (
          <p className="text-[11px] text-text-muted leading-relaxed">
            Load a repository to browse its files.
          </p>
        ) : filtered.length === 0 ? (
          <p className="text-[11px] text-text-muted">No files match “{query}”.</p>
        ) : (
          tree.children.map((child, i) => (
            <Row
              key={child.path}
              node={child}
              prefix=""
              isLast={i === tree.children.length - 1}
              depth={0}
              expanded={effectiveExpanded}
              onToggleDir={toggleDir}
              onDownload={(p) => void doDownload(p)}
              downloading={downloading}
              onSelectFile={onSelectFile}
              selectedPath={selectedPath}
              hideDownload={hideDownload}
            />
          ))
        )}
      </div>
    </>
  );

  if (embedded) return <div className="flex flex-col gap-2 min-h-0">{body}</div>;

  return (
    <section className="card p-4 flex flex-col gap-2 overflow-hidden min-w-0">
      {body}
    </section>
  );
}
