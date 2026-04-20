import { ArrowRight, Database, MessageSquare, Mail, Ticket, Globe, Bot, CheckCircle2 } from "lucide-react";
import { AiAvatar } from "@/components/AiAvatar";
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
        <AiAvatar size="lg" />
      </div>

      {/* Text */}
      <div className="space-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-600">
          <CheckCircle2 className="h-3 w-3" />
          Workflow ready
        </span>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
          Name your agent
        </h2>
        <p className="text-sm text-slate-500">
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
          className="w-full h-12 rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-ai-brand/40 focus:ring-2 focus:ring-ai-brand/10 transition-all duration-200"
        />

        <button
          type="submit"
          disabled={isButtonDisabled}
          className={[
            "w-full h-12 rounded-xl text-sm font-semibold text-white transition-all duration-150 inline-flex items-center justify-center gap-2",
            isButtonDisabled
              ? "bg-slate-300 cursor-not-allowed"
              : "bg-ai-brand shadow-lg shadow-ai-brand/25 hover:bg-ai-brand-hover hover:shadow-xl hover:shadow-ai-brand/30",
          ].join(" ")}
        >
          Continue
          <ArrowRight size={16} strokeWidth={2.5} />
        </button>
      </form>

      {/* Setup tips */}
      {tips.length > 0 && (
        <div className="pt-2 space-y-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            After setup, you'll need to configure
          </p>
          <div className="space-y-2">
            {tips.map((tip) => (
              <div
                key={tip.label}
                className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-left"
              >
                <div className="h-8 w-8 shrink-0 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500">
                  {tip.icon}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-700">{tip.label}</p>
                  <p className="text-xs text-slate-400">{tip.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
