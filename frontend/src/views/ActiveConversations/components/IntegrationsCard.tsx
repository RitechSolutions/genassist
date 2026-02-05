import { useState, useEffect } from "react";
import { Mail, Headset, MessageSquare, MessageCircle, Calendar, Settings } from "lucide-react";
import { Card } from "@/components/card";
import { IntegrationWorkflowsDialog } from "./IntegrationWorkflowsDialog";
import { fetchDashboardIntegrations } from "@/services/dashboard";
import type { IntegrationItem as ApiIntegrationItem } from "@/interfaces/dashboard.interface";
import { useNavigate } from "react-router-dom";

type IconType = "mail" | "headset" | "slack" | "whatsapp" | "calendar" | "other";

interface Integration {
  id: string;
  name: string;
  description: string;
  icon: IconType;
  iconColor: string;
  bgColor: string;
  type: string;
}

interface IntegrationsCardProps {
  integrations?: Integration[];
  loading?: boolean;
  onViewAll?: () => void;
}

const getIconTypeFromIntegrationType = (type: string): IconType => {
  const typeMap: Record<string, IconType> = {
    gmail: "mail",
    zendesk: "headset",
    slack: "slack",
    whatsapp: "whatsapp",
    microsoft: "calendar",
    jira: "other",
    other: "other",
  };
  return typeMap[type.toLowerCase()] || "other";
};

const transformApiIntegration = (item: ApiIntegrationItem): Integration => ({
  id: item.id,
  name: item.name,
  description: item.description || getDefaultDescription(item.type),
  icon: getIconTypeFromIntegrationType(item.type),
  iconColor: "text-green-700",
  bgColor: "bg-green-100",
  type: item.type,
});

const getDefaultDescription = (type: string): string => {
  const descriptions: Record<string, string> = {
    Gmail: "Send via Gmail",
    Zendesk: "Create support tickets",
    Slack: "Send Slack messages",
    WhatsApp: "Send WhatsApp messages",
    Microsoft: "Microsoft 365 integration",
    Jira: "Create Jira issues",
    Other: "Custom integration",
  };
  return descriptions[type] || "Custom integration";
};

const getIcon = (iconType: IconType) => {
  const iconProps = { className: "w-5 h-5" };

  switch (iconType) {
    case "mail":
      return <Mail {...iconProps} />;
    case "headset":
      return <Headset {...iconProps} />;
    case "slack":
      return <MessageSquare {...iconProps} />;
    case "whatsapp":
      return <MessageCircle {...iconProps} />;
    case "calendar":
      return <Calendar {...iconProps} />;
    case "other":
    default:
      return <Settings {...iconProps} />;
  }
};

export function IntegrationsCard({
  integrations: propIntegrations,
  loading: propLoading,
  onViewAll,
}: IntegrationsCardProps) {
  const navigate = useNavigate();
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If integrations are passed as props, use them
    if (propIntegrations) {
      setIntegrations(propIntegrations);
      setLoading(propLoading || false);
      return;
    }

    // Otherwise fetch from API
    const fetchIntegrations = async () => {
      setLoading(true);
      try {
        const response = await fetchDashboardIntegrations();
        if (response?.integrations) {
          setIntegrations(response.integrations.map(transformApiIntegration));
        }
      } catch (error) {
        console.error("Error fetching integrations:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchIntegrations();
  }, [propIntegrations, propLoading]);

  const handleIntegrationClick = (integration: Integration) => {
    setSelectedIntegration(integration);
    setIsDialogOpen(true);
  };

  const handleViewAll = () => {
    if (onViewAll) {
      onViewAll();
    } else {
      navigate("/app-settings");
    }
  };

  return (
    <>
      <Card className="bg-white border border-border rounded-xl overflow-hidden shadow-sm animate-fade-up">
        {/* Header */}
        <div className="bg-white flex items-center justify-between p-6">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-foreground">Integrations</h3>
          </div>
          <button
            onClick={handleViewAll}
            className="text-sm font-medium text-foreground hover:underline hidden"
          >
            View all
          </button>
        </div>

        {/* Integrations List */}
        <div className="flex flex-col gap-2 px-4 pb-4">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 bg-gray-200 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : integrations.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No integrations configured yet.</p>
              <button
                onClick={handleViewAll}
                className="mt-2 text-sm text-primary hover:underline"
              >
                Configure integrations
              </button>
            </div>
          ) : (
            integrations.map((integration) => (
              <div
                key={integration.id}
                onClick={() => handleIntegrationClick(integration)}
                className="flex gap-3 items-center p-2 hover:bg-muted/30 rounded-lg transition-colors cursor-pointer"
              >
                {/* Icon */}
                <div className={`${integration.bgColor} flex items-center p-2 rounded-lg shrink-0`}>
                  <div className={integration.iconColor}>
                    {getIcon(integration.icon)}
                  </div>
                </div>

                {/* Content */}
                <div className="flex flex-col flex-1 min-w-0">
                  <p className="text-sm font-semibold text-accent-foreground truncate">
                    {integration.name}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {integration.description}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      <IntegrationWorkflowsDialog
        integration={selectedIntegration}
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
      />
    </>
  );
}

export default IntegrationsCard;
