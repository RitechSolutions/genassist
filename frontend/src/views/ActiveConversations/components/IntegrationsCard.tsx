import { useState } from "react";
import { Mail, Headset, MessageSquare, MessageCircle, Calendar } from "lucide-react";
import { Card } from "@/components/card";
import { IntegrationWorkflowsDialog } from "./IntegrationWorkflowsDialog";

interface Integration {
  id: string;
  name: string;
  description: string;
  icon: "mail" | "headset" | "slack" | "whatsapp" | "calendar";
  iconColor: string;
  bgColor: string;
}

interface IntegrationsCardProps {
  integrations?: Integration[];
  loading?: boolean;
  onViewAll?: () => void;
}

const mockIntegrations: Integration[] = [
  {
    id: "1",
    name: "Email Read/Send",
    description: "Send via Gmail",
    icon: "mail",
    iconColor: "text-green-700",
    bgColor: "bg-green-100",
  },
  {
    id: "2",
    name: "Zendesk Ticket",
    description: "Create support tickets",
    icon: "headset",
    iconColor: "text-green-700",
    bgColor: "bg-green-100",
  },
  {
    id: "3",
    name: "Slack Messenger",
    description: "Send Slack messages",
    icon: "slack",
    iconColor: "text-green-700",
    bgColor: "bg-green-100",
  },
  {
    id: "4",
    name: "WhatsApp",
    description: "Send WhatsApp messages",
    icon: "whatsapp",
    iconColor: "text-green-700",
    bgColor: "bg-green-100",
  },
  {
    id: "5",
    name: "Calendar",
    description: "Schedule events",
    icon: "calendar",
    iconColor: "text-green-700",
    bgColor: "bg-green-100",
  },
];

const getIcon = (iconType: Integration["icon"]) => {
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
    default:
      return <Mail {...iconProps} />;
  }
};

export function IntegrationsCard({ 
  integrations = mockIntegrations, 
  loading, 
  onViewAll 
}: IntegrationsCardProps) {
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleIntegrationClick = (integration: Integration) => {
    setSelectedIntegration(integration);
    setIsDialogOpen(true);
  };

  return (
    <>
      <Card className="bg-white border border-border rounded-xl overflow-hidden shadow-sm">
        {/* Header */}
        <div className="bg-white flex items-center justify-between p-6">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-foreground">Integrations</h3>
          </div>
          <button
            onClick={onViewAll}
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
