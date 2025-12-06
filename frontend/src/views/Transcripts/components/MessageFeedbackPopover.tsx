import { MessageCircle } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { Textarea } from "@/components/textarea";
import { Button } from "@/components/button";

type MessageFeedbackPopoverProps = {
  isOpen: boolean;
  hasFeedbackMessage: boolean;
  text: string;
  onOpenChange: (open: boolean) => void;
  onTextChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
};

export function MessageFeedbackPopover({
  isOpen,
  hasFeedbackMessage,
  text,
  onOpenChange,
  onTextChange,
  onSave,
  onCancel,
}: MessageFeedbackPopoverProps) {
  return (
    <Popover open={isOpen} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          className={`p-2 rounded-lg shadow-sm border hover:opacity-80 ${
            hasFeedbackMessage
              ? "bg-black border-black"
              : "bg-white border-gray-200 hover:bg-gray-100"
          }`}
          title="Add feedback message"
        >
          <MessageCircle
            className={`w-4 h-4 ${
              hasFeedbackMessage ? "text-white fill-current" : "text-gray-500"
            }`}
          />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 z-50" side="bottom" align="start">
        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">
              Enter the feedback for this message
            </h4>
          </div>
          <div className="grid gap-2">
            <Textarea
              placeholder="Enter message"
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              rows={4}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              onClick={onSave}
              className="bg-blue-600 text-white hover:bg-blue-700"
            >
              Save
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
