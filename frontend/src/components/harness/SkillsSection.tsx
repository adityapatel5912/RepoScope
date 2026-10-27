import { Sparkles, FileCode, AlertCircle } from "lucide-react";
import type { HarnessSkill } from "../../api/client";

interface Props {
  skills: HarnessSkill[];
  loading: boolean;
  error?: string | null;
}

export default function SkillsSection({ skills, loading, error }: Props) {
  if (loading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center gap-2 text-text-muted">
        <span className="btn-spinner" />
        <span className="text-xs">Loading skill descriptors...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-800 text-xs flex items-center gap-2">
        <AlertCircle size={16} />
        <span>Failed to load skills: {error}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="p-3 rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 text-xs text-text-secondary flex items-start gap-2.5">
        <Sparkles size={16} className="text-accent-cyan shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-text-primary">Phase 4 Skills Preview: </span>
          RepoScope defines 5 specialized skills for AI coding agents. In Phase 3, descriptors are visible; full executable SKILL.md bundles are enabled in Phase 4.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="harness-skills-list">
        {skills.map((skill) => (
          <div
            key={skill.id}
            className="card p-3.5 flex flex-col justify-between gap-3 border-border-subtle hover:border-accent-cyan/40 transition-colors"
            data-testid={`harness-skill-${skill.id}`}
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <h4 className="text-xs font-bold text-text-primary">{skill.label}</h4>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider bg-bg-panel-alt border border-border-subtle text-text-muted shrink-0">
                  {skill.content_available ? "Ready" : "Available in Phase 4"}
                </span>
              </div>
              <p className="text-2xs text-text-secondary leading-relaxed mb-3">
                {skill.description}
              </p>
            </div>

            <div className="pt-2 border-t border-border-hairline flex flex-col gap-1.5 text-[11px]">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-2xs text-text-muted font-mono uppercase tracking-wider">Targets:</span>
                {skill.targets.map((target) => (
                  <span
                    key={target}
                    className="px-1.5 py-0.5 rounded bg-bg-panel-alt text-2xs font-mono text-text-secondary border border-border-subtle"
                  >
                    {target}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <FileCode size={11} className="text-text-muted shrink-0" />
                <span className="text-2xs text-text-muted font-mono">{skill.files.join(", ")}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
