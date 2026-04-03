import { ArrowRight, Sparkles, Database, MessageSquare, Mail, Ticket, Globe, Bot, CheckCircle2 } from "lucide-react";
import type { WorkflowDraft } from "@/views/Onboarding/utils/extractWorkflowDraft";

interface SetupTip {
  icon: React.ReactNode;
  label: string;
  description: string;
}

/** Derive setup tips from the workflow nodes that need manual configuration. */
const getSetupTips = (draft: WorkflowDraft | null): SetupTip[] => {
  if (!draft) return [];
  const tips: SetupTip[] = [];
  const nodeNames = new Set(draft.workflow.map((n) => n.node_name));

  if (nodeNames.has("knowledgeBaseNode")) {
    tips.push({
      icon: <Database className="h-4 w-4" />,
      label: "Connect Knowledge Base",
      description: "Upload your documents or connect a data source",
    });
  }
  if (nodeNames.has("slackMessageNode")) {
    tips.push({
      icon: <MessageSquare className="h-4 w-4" />,
      label: "Connect Slack",
      description: "Authorize your Slack workspace",
    });
  }
  if (nodeNames.has("gmailNode")) {
    tips.push({
      icon: <Mail className="h-4 w-4" />,
      label: "Connect Gmail",
      description: "Authorize your Google account",
    });
  }
  if (nodeNames.has("jiraNode")) {
    tips.push({
      icon: <Ticket className="h-4 w-4" />,
      label: "Connect Jira",
      description: "Add your Jira project URL and API token",
    });
  }
  if (nodeNames.has("apiCallNode")) {
    tips.push({
      icon: <Globe className="h-4 w-4" />,
      label: "Configure API",
      description: "Set the endpoint URL and authentication",
    });
  }
  if (nodeNames.has("agentNode")) {
    tips.push({
      icon: <Bot className="h-4 w-4" />,
      label: "Review Agent Prompt",
      description: "Customize the tone and instructions",
    });
  }

  return tips;
};

interface OnboardingNameAgentProps {
  value: string;
  disabled?: boolean;
  onChange: (val: string) => void;
  onContinue: () => void;
  workflowDraft?: WorkflowDraft | null;
}

export const OnboardingNameAgent = ({
  value,
  disabled = false,
  onChange,
  onContinue,
  workflowDraft = null,
}: OnboardingNameAgentProps) => {
  const isButtonDisabled = disabled || !value.trim();
  const tips = getSetupTips(workflowDraft);

  return (
    <div className="w-full max-w-md text-center space-y-6 animate-fade-up">
      {/* Icon */}
      <div className="flex justify-center">
        <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] flex items-center justify-center shadow-lg shadow-[#5b4bff]/20">
          <Sparkles className="h-6 w-6 text-white" />
        </div>
      </div>

      {/* Text */}
      <div className="space-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f0fdf4] px-3 py-1 text-xs font-semibold text-[#16a34a]">
          <CheckCircle2 className="h-3 w-3" />
          Workflow ready
        </span>
        <h2 className="text-2xl font-bold text-[#0f172a] tracking-tight">
          Name your agent
        </h2>
        <p className="text-sm text-[#64748b]">
          Give your agent a name to identify it in the dashboard.
        </p>
      </div>

      {/* Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onContinue();
        }}
        className="space-y-4"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. Customer Support Bot"
          disabled={disabled}
          className="w-full h-12 rounded-xl border border-[#e2e8f0] bg-white px-4 text-sm text-[#0f172a] outline-none placeholder:text-[#94a3b8] focus:border-[#5b4bff]/40 focus:ring-2 focus:ring-[#5b4bff]/10 transition-all duration-200"
        />

        <button
          type="submit"
          disabled={isButtonDisabled}
          className={[
            "w-full h-12 rounded-xl text-sm font-semibold text-white transition-all duration-150 inline-flex items-center justify-center gap-2",
            isButtonDisabled
              ? "bg-[#cbd5e1] cursor-not-allowed"
              : "bg-[#5b4bff] shadow-lg shadow-[#5b4bff]/25 hover:bg-[#4f46e5] hover:shadow-xl hover:shadow-[#5b4bff]/30",
          ].join(" ")}
        >
          Continue
          <ArrowRight size={16} strokeWidth={2.5} />
        </button>
      </form>

      {/* Setup tips */}
      {tips.length > 0 && (
        <div className="pt-2 space-y-3">
          <p className="text-xs font-medium text-[#94a3b8] uppercase tracking-wider">
            After setup, you'll need to configure
          </p>
          <div className="space-y-2">
            {tips.map((tip) => (
              <div
                key={tip.label}
                className="flex items-center gap-3 rounded-xl border border-[#e2e8f0] bg-white px-4 py-2.5 text-left"
              >
                <div className="h-8 w-8 shrink-0 rounded-lg bg-[#f1f5f9] flex items-center justify-center text-[#64748b]">
                  {tip.icon}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#334155]">{tip.label}</p>
                  <p className="text-xs text-[#94a3b8]">{tip.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
