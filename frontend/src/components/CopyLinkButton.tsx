import { useState } from "react";
import { Check, Share2 } from "lucide-react";

import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";
import { toast } from "@/hooks/useToast";

/** Copies a share link and shows a check mark for two seconds */
export function CopyLinkButton({
  url,
  description,
  className,
}: {
  url: string;
  description: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      toast({ title: "Couldn't copy the link", variant: "destructive" });
      return;
    }
    setCopied(true);
    toast({ title: "Link copied to clipboard", description });
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn(
        "h-7 w-7 p-0 transition-colors",
        copied && "text-green-600 dark:text-green-400",
        className,
      )}
      title="Copy share link"
      aria-label="Copy share link"
      disabled={copied}
      onClick={() => void copy()}
    >
      {copied ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
    </Button>
  );
}
