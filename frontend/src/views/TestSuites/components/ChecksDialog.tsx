import React from "react";
import { Button } from "@/components/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/dialog";
import type { ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import type { CheckConversation } from "../helpers/checks";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";
import { ChecksList } from "./ChecksList";

interface ChecksDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  checks: ScenarioCheck[];
  description: string;
  conversations: CheckConversation[];
  conversationsReady: boolean;
  /** Flags tools, steps and routers the workflow no longer has. */
  catalog?: EvaluationCatalog | null;
  /** Buttons after Close. */
  actions?: React.ReactNode;
}

/** Checks, read only, in a dialog so a long list does not push the page down. */
export const ChecksDialog: React.FC<ChecksDialogProps> = ({
  open,
  onOpenChange,
  checks,
  description,
  conversations,
  conversationsReady,
  catalog,
  actions,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="flex max-h-[85vh] max-w-3xl flex-col gap-0 p-0">
      <DialogHeader className="border-b px-6 py-4">
        <DialogTitle>Checks ({checks.length})</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <ChecksList checks={checks} conversations={conversations} conversationsReady={conversationsReady} catalog={catalog} />
      </div>
      <DialogFooter className="gap-2 border-t px-6 py-4">
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Close
        </Button>
        {actions}
      </DialogFooter>
    </DialogContent>
  </Dialog>
);
