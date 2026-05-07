import { useMemo, useRef, useState } from "react";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Loader2, Square, HeartPulse, MessageSquare } from "lucide-react";
import { toast } from "react-hot-toast";
import type { LocalFineTuneDeployment } from "@/interfaces/localFineTune.interface";
import { stopDeployment, checkDeploymentHealth } from "@/services/localFineTune";
import { LocalFineTuneTestDialog } from "@/views/LocalFineTune/components/LocalFineTuneTestDialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";

function formatShortDate(value: unknown): string {
  if (value == null || value === "") return "—";
  const d = new Date(String(value));
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderDeploymentStatus(deployment: LocalFineTuneDeployment) {
  const s = String(deployment.status ?? "").toLowerCase();
  if (s === "starting") {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
        <span className="font-medium text-foreground capitalize">Starting</span>
      </div>
    );
  }
  if (s === "running") {
    return (
      <Badge variant="outline" className="px-3 py-1 text-xs font-medium border-teal-200 bg-teal-50 text-teal-800">
        Running
      </Badge>
    );
  }
  if (s === "failed") {
    const msg = deployment.error_message?.trim();
    const badge = (
      <Badge variant="destructive" className="px-3 py-1 text-xs font-medium">
        Failed
      </Badge>
    );
    if (!msg) return badge;
    return (
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex flex-col gap-0.5 cursor-default w-fit">
              {badge}
              <span className="text-[11px] text-destructive truncate max-w-[180px]">{msg}</span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-xs break-words">
            {msg}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
  if (s === "stopped") {
    return (
      <Badge variant="secondary" className="px-3 py-1 text-xs font-medium bg-muted text-muted-foreground">
        Stopped
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="px-3 py-1 text-xs font-medium capitalize">
      {s}
    </Badge>
  );
}

interface LocalFineTuneDeploymentsCardProps {
  deployments: LocalFineTuneDeployment[];
  setDeployments: React.Dispatch<React.SetStateAction<LocalFineTuneDeployment[]>>;
  loading: boolean;
  error: string | null;
  searchQuery: string;
}

export function LocalFineTuneDeploymentsCard({
  deployments,
  setDeployments,
  loading,
  error,
  searchQuery,
}: LocalFineTuneDeploymentsCardProps) {
  const [deploymentToStop, setDeploymentToStop] = useState<LocalFineTuneDeployment | null>(null);
  const [isStopDialogOpen, setIsStopDialogOpen] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [checkingHealthId, setCheckingHealthId] = useState<string | null>(null);
  const healthCheckInFlight = useRef<Set<string>>(new Set());
  const [deploymentToTest, setDeploymentToTest] = useState<LocalFineTuneDeployment | null>(null);

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return deployments.filter((d) =>
      [d.id, d.model_path, d.status, String(d.port), String(d.gpu_id)]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase())
        .some((s) => s.includes(q))
    );
  }, [deployments, searchQuery]);

  const isRecentDeployment = (deployment: LocalFineTuneDeployment) => {
    if (!deployment.created_at) return false;
    return Date.now() - new Date(deployment.created_at).getTime() < 20_000;
  };

  const handleHealthCheck = async (deployment: LocalFineTuneDeployment) => {
    if (healthCheckInFlight.current.has(deployment.id)) return;
    healthCheckInFlight.current.add(deployment.id);
    setCheckingHealthId(deployment.id);
    try {
      const result = await checkDeploymentHealth(deployment.id);
      if (result.status === "healthy") {
        toast.success(`Healthy — ${result.details}`);
      } else if (isRecentDeployment(deployment)) {
        toast(`Service may need a few seconds to become accessible`, { icon: "⚠️" });
      } else {
        toast.error(`Unhealthy — ${result.details}`);
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        toast.error("Session expired — please refresh the page");
      } else if (isRecentDeployment(deployment)) {
        toast(`Service may need a few seconds to become accessible`, { icon: "⚠️" });
      } else {
        toast.error("Health check failed");
      }
    } finally {
      healthCheckInFlight.current.delete(deployment.id);
      setCheckingHealthId(null);
    }
  };

  const handleStopConfirm = async () => {
    if (!deploymentToStop) return;
    setIsStopping(true);
    try {
      await stopDeployment(deploymentToStop.id);
      setDeployments((prev) =>
        prev.map((d) =>
          d.id === deploymentToStop.id ? { ...d, status: "stopped" } : d
        )
      );
      toast.success("Deployment stopped");
    } catch {
      toast.error("Failed to stop deployment");
    } finally {
      setIsStopping(false);
      setIsStopDialogOpen(false);
      setDeploymentToStop(null);
    }
  };

  const isActive = (d: LocalFineTuneDeployment) => {
    const s = String(d.status).toLowerCase();
    return s === "running" || s === "starting";
  };

  const columns = useMemo<Column<LocalFineTuneDeployment>[]>(
    () => [
      {
        header: "Deployment ID",
        key: "deployment_id",
        cell: (d) => {
          const modelSegment = d.model_path?.split("/").filter(Boolean).pop() ?? null;
          return (
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="font-medium text-zinc-800 truncate font-mono text-sm">{d.id}</span>
              {modelSegment ? (
                <span className="text-xs text-muted-foreground truncate">{modelSegment}</span>
              ) : null}
            </div>
          );
        },
      },
      {
        header: "Status",
        key: "status",
        cell: (d) => renderDeploymentStatus(d),
      },
      {
        header: "GPU / Port",
        key: "gpu_port",
        cell: (d) => (
          <span className="text-sm text-muted-foreground tabular-nums">
            {d.gpu_id != null ? `GPU ${d.gpu_id}` : "GPU auto"} · :{d.port}
          </span>
        ),
      },
      {
        header: "Created",
        key: "created_at",
        cell: (d) => (
          <span className="text-xs text-zinc-500 tabular-nums">
            {formatShortDate(d.created_at)}
          </span>
        ),
      },
      {
        header: "",
        key: "actions",
        cell: (d) => (
          <div className="flex items-center gap-1">
            {isActive(d) && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                title="Test model"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeploymentToTest(d);
                }}
              >
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Check health"
              disabled={checkingHealthId === d.id}
              onClick={(e) => {
                e.stopPropagation();
                void handleHealthCheck(d);
              }}
            >
              {checkingHealthId === d.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <HeartPulse className="h-4 w-4 text-muted-foreground" />
              )}
            </Button>
            {isActive(d) && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                title="Stop deployment"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeploymentToStop(d);
                  setIsStopDialogOpen(true);
                }}
              >
                <Square className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </div>
        ),
      },
    ],
    [checkingHealthId]
  );

  return (
    <>
      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        emptyMessage="No deployments yet"
        notFoundMessage="No deployments matching your search"
        keyExtractor={(d) => d.id}
        pageSize={10}
      />

      {deploymentToTest && (
        <LocalFineTuneTestDialog
          isOpen={Boolean(deploymentToTest)}
          onOpenChange={(open) => { if (!open) setDeploymentToTest(null); }}
          deployment={deploymentToTest}
        />
      )}

      <ConfirmDialog
        isOpen={isStopDialogOpen}
        onOpenChange={setIsStopDialogOpen}
        onConfirm={handleStopConfirm}
        isInProgress={isStopping}
        itemName={deploymentToStop?.id}
        title="Stop deployment?"
        description={`This will terminate the vLLM process for "${deploymentToStop?.id}". The model will no longer be accessible.`}
        primaryButtonText="Stop"
        secondaryButtonText="Cancel"
        onCancel={() => setDeploymentToStop(null)}
      />
    </>
  );
}