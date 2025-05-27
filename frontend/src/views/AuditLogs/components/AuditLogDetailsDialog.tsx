import { useState, useEffect } from "react";
import { tryParse } from "@/helpers/utils";
import {
  Dialog,
  DialogDescription,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { JsonViewer } from "./JsonViewer";
import { Loader2 } from "lucide-react";
import { AuditLogDetailsDialogProps } from "@/interfaces/audit-log.interface";
import { fetchAuditLogDetails } from "@/services/auditLogs";

export function AuditLogDetailsDialog({
  isOpen,
  onOpenChange,
  auditLogId,
}: AuditLogDetailsDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsedJsonChanges, setParsedJsonChanges] = useState<any | string | null>(null);

  useEffect(() => {
    if (isOpen && auditLogId) {
      setLoading(true);
      setError(null);
      fetchAuditLogDetails(auditLogId)
        .then((data) => {
          if (data?.json_changes) {
            try {
              let parsed = data.json_changes;
              if (typeof parsed === "string") {
                parsed = JSON.parse(parsed);
              }

              const recursiveParse = (obj: any): any => {
                if (typeof obj === "string") {
                  try {
                    return JSON.parse(obj);
                  } catch {
                    return obj;
                  }
                } else if (typeof obj === "object" && obj !== null) {
                  for (const key in obj) {
                    if (Object.prototype.hasOwnProperty.call(obj, key)) {
                      obj[key] = recursiveParse(obj[key]);
                    }
                  }
                }
                return obj;
              };

              parsed = recursiveParse(parsed);

              const cleanParsed = Object.fromEntries(
                Object.entries(parsed).map(([key, value]) => {
                  if (
                    typeof value === "object" &&
                    value !== null &&
                    "old" in value &&
                    "new" in value
                  ) {
                    const cleanOld = tryParse(value.old);
                    const cleanNew = tryParse(value.new);
                    const isArrayDiff =
                      Array.isArray(cleanOld) && Array.isArray(cleanNew);

                    return [
                      key,
                      isArrayDiff
                        ? {
                            [`${key} (Before)`]: cleanOld,
                            [`${key} (After)`]: cleanNew,
                          }
                        : { [`${key} (Before)`]: cleanOld, [`${key} (After)`]: cleanNew },
                    ];
                  }
                  return [key, value];
                })
              );

              setParsedJsonChanges(cleanParsed);
            } catch {
              setParsedJsonChanges("Error parsing JSON data.");
            }
          } else if (data) {
            setParsedJsonChanges("No changes available in this audit log.");
          } else {
            setError("No audit log details available.");
            setParsedJsonChanges(null);
          }
        })
        .catch(() => {
          setError("An error occurred while fetching the details.");
          setParsedJsonChanges(null);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isOpen, auditLogId]);

  if (loading) {
    return (
      <Dialog open={isOpen} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Loading Details...</DialogTitle>
            <DialogDescription>Preparing the JSON data ...</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button disabled>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Audit Log Details</DialogTitle>
        </DialogHeader>
        <div className="p-4">
          {error ? (
            <p className="text-red-500">{error}</p>
          ) : parsedJsonChanges ? (
            <JsonViewer jsonData={parsedJsonChanges} />
          ) : (
            <p>No JSON changes available for this audit log.</p>
          )}
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}