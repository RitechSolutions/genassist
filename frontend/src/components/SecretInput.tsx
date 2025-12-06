import * as React from "react";
import { Eye, EyeOff, Copy } from "lucide-react";
import toast from "react-hot-toast";

import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { cn } from "@/helpers/utils";

export type SecretInputProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "value"
> & {
  value: string;
};

const SecretInput = React.forwardRef<HTMLInputElement, SecretInputProps>(
  ({ className, value, ...props }, ref) => {
    const [show, setShow] = React.useState(false);

    const copyToClipboard = (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      navigator.clipboard.writeText(value);
      toast.success("Copied to clipboard.");
    };

    const toggleVisibility = (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setShow((s) => !s);
    };

    return (
      <div className="relative">
        <Input
          ref={ref}
          readOnly
          type={show ? "text" : "password"}
          value={value}
          className={cn("pr-20", className)}
          {...props}
        />
        <div className="absolute top-1/2 right-2 -translate-y-1/2 flex items-center space-x-1 z-10">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 pointer-events-auto"
            onClick={toggleVisibility}
            title={show ? "Hide" : "Show"}
          >
            {show ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 pointer-events-auto"
            onClick={copyToClipboard}
            title="Copy to clipboard"
            disabled={!value}
          >
            <Copy className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }
);
SecretInput.displayName = "SecretInput";

export { SecretInput };
