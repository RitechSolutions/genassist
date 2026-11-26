import { TemplateListItem } from "@/interfaces/template.interface";

interface DialogCopy {
  title: string;
  description: string;
}

type CopyInput = Partial<Pick<TemplateListItem, "publish_status" | "title">>;

// The dialog only shows its own description, so the text names the template.
const named = (template: CopyInput): string => (template.title ? `"${template.title}"` : "this template");

// Delete also withdraws the shared copy. The text covers pending and approved alike, since the card's status can be stale.
export const deleteConfirmation = (template: CopyInput): DialogCopy => {
  const shared = template.publish_status === "approved" || template.publish_status === "pending";
  return {
    title: "Delete this template?",
    description: shared
      ? `This permanently deletes ${named(template)}. Its shared copy, published or waiting for review, is removed for every tenant too. Agents already installed from it keep working.`
      : `This permanently deletes ${named(template)}. Agents already created from it keep working.`,
  };
};

export const withdrawConfirmation = (template: CopyInput): DialogCopy => {
  const name = named(template);
  return {
    title: "Withdraw from the library?",
    description: `${name.charAt(0).toUpperCase()}${name.slice(1)} leaves the library and the review queue. Agents already installed from it keep working. Publishing it again means a new review.`,
  };
};

// The reviewer's reason, shown only on the author's own rejected card.
export const rejectionNote = (
  template: Pick<TemplateListItem, "publish_status" | "is_global" | "rejection_reason">,
): string | null => {
  const reason = template.rejection_reason?.trim();
  return !template.is_global && template.publish_status === "rejected" && reason ? reason : null;
};
