import React from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";

interface DeleteGroupDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** Number of group containers being deleted. */
  groupCount: number;
  /** Number of workflow nodes inside those groups. */
  memberCount: number;
  /** Other selected nodes deleted either way. */
  otherCount: number;
  onDeleteGroupOnly: () => void;
  onDeleteWithContents: () => void;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/**
 * Deleting a group never silently removes the workflow nodes inside it: the default action removes
 * only the container (its nodes stay where they are), and deleting the contents is a separate,
 * explicitly labelled choice.
 */
const DeleteGroupDialog: React.FC<DeleteGroupDialogProps> = ({
  isOpen,
  onOpenChange,
  groupCount,
  memberCount,
  otherCount,
  onDeleteGroupOnly,
  onDeleteWithContents,
}) => {
  const groupLabel = groupCount === 1 ? "this group" : `these ${groupCount} groups`;
  return (
    <AlertDialog open={isOpen} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {groupCount === 1 ? "group" : "groups"}?</AlertDialogTitle>
          <AlertDialogDescription>
            {memberCount > 0
              ? `${groupLabel[0].toUpperCase()}${groupLabel.slice(1)} contains ${plural(
                  memberCount,
                  "node"
                )}. You can remove just the group and keep its nodes on the canvas, or delete the nodes too.`
              : `${groupLabel[0].toUpperCase()}${groupLabel.slice(1)} is empty.`}
            {otherCount > 0 &&
              ` The other ${plural(otherCount, "selected node")} will be deleted either way.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2 sm:gap-0">
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          {memberCount > 0 && (
            <AlertDialogAction
              onClick={onDeleteWithContents}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 focus:ring-destructive"
            >
              Delete group and {plural(memberCount, "node")}
            </AlertDialogAction>
          )}
          <AlertDialogAction onClick={onDeleteGroupOnly}>
            {groupCount === 1 ? "Delete group only" : "Delete groups only"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default DeleteGroupDialog;
