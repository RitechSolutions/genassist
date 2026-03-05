import { AlertCircle, CheckCircle, HelpCircle, Loader2, Plug } from "lucide-react";
import { Alert, AlertDescription } from "@/components/alert";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import type { ConnectionStatus } from "@/interfaces/connectionStatus.interface";

interface ConnectionTestPanelProps {
  isTesting: boolean;
  testStatus: ConnectionStatus | null;
  onTest: () => void;
  disabled?: boolean;
}

export function ConnectionTestPanel({
  isTesting,
  testStatus,
  onTest,
  disabled = false,
}: ConnectionTestPanelProps) {
  return (
    <div className="space-y-2">
      <div className={`flex justify-end${isTesting ? " invisible" : ""}`}>
        {testStatus?.status === "Connected" ? (
          <Badge variant="success">
            <CheckCircle className="w-3 h-3 mr-1" /> Connected
          </Badge>
        ) : testStatus?.status === "Error" ? (
          <Badge variant="destructive">
            <AlertCircle className="w-3 h-3 mr-1" /> Error
          </Badge>
        ) : (
          <Badge variant="outline">
            <HelpCircle className="w-3 h-3 mr-1" /> Untested
          </Badge>
        )}
      </div>
      {isTesting ? (
        <Alert>
          <Loader2 className="h-4 w-4 animate-spin" />
          <AlertDescription>Testing connection, please wait…</AlertDescription>
        </Alert>
      ) : testStatus?.status === "Connected" ? (
        <Alert variant="success">
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>{testStatus.message}</AlertDescription>
        </Alert>
      ) : testStatus?.status === "Error" ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Connection failed. Please verify your settings.
            {testStatus.message && (
              <span className="block mt-1 text-xs opacity-75 break-all">
                {testStatus.message}
              </span>
            )}
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            This configuration has not been tested. Verify it works before
            saving.
          </AlertDescription>
        </Alert>
      )}
      <Button
        type="button"
        className="w-full"
        onClick={onTest}
        disabled={isTesting || disabled}
      >
        {isTesting ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Plug className="mr-2 h-4 w-4" />
        )}
        Test Connection
      </Button>
    </div>
  );
}
