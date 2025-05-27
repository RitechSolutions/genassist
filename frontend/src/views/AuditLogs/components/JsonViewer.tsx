import { useState } from "react";
import { Card } from "@/components/card";
import { JsonViewerProps } from "@/interfaces/audit-log.interface";
import { ScrollArea } from "@/components/scroll-area";
import { cn } from "@/helpers/utils";
import { Button } from "@/components/button";
import { Check, Clipboard, Download, Loader2 } from "lucide-react";

const CollapsibleJSON = ({
  value,
  expanded,
  level = 0,
  label,
}: {
  value: any;
  expanded: boolean;
  level?: number;
  label?: string;
}) => {
  const [collapsed, setCollapsed] = useState(!expanded);

  const isObject = typeof value === "object" && value !== null;
  const isArray = Array.isArray(value);

  if (value === null || value === undefined) {
    return (
      <div className={`pl-${level * 2}`}>
        {label && <strong>{label}: </strong>}
        <span className="text-muted-foreground">null</span>
      </div>
    );
  }

  if (isObject || isArray) {
    const typeLabel = isArray ? "Array" : "Object";

    return (
      <div>
        <div
          className={`cursor-pointer text-blue-500 pl-${level * 2}`}
          onClick={() => setCollapsed((prev) => !prev)}
        >
          {collapsed ? "▶" : "▼"}{" "}
          {label ? (
            <>
              <strong>{label}</strong> ({typeLabel})
            </>
          ) : (
            <>{typeLabel}</>
          )}
        </div>
        {!collapsed && (
          <div className="ml-4">
            {isArray
              ? value.map((item, index) => (
                  <CollapsibleJSON
                    key={index}
                    value={item}
                    expanded={false}
                    level={level + 1}
                    label={String(index)}
                  />
                ))
              : Object.keys(value).map((key) => (
                  <CollapsibleJSON
                    key={key}
                    value={value[key]}
                    expanded={false}
                    level={level + 1}
                    label={key}
                  />
                ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`pl-${level * 2}`}>
      {label && <strong>{label}: </strong>}
      <span>{JSON.stringify(value)}</span>
    </div>
  );
};

export function JsonViewer({ jsonData, className }: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  if (!jsonData) {
    return <p className="text-muted-foreground">No data available</p>;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(jsonData, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy JSON", err);
    }
  };

  const handleDownload = () => {
    setDownloading(true);

    const blob = new Blob([JSON.stringify(jsonData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data.json";
    link.click();
    URL.revokeObjectURL(url);

    setTimeout(() => {
      setDownloading(false);
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 2000); // reset
    }, 1000);
  };

  return (
    <Card className={cn("p-4", className)}>
      <div className="flex justify-end gap-2 mb-2">
        <Button
          size="sm"
          variant="outline"
          onClick={handleCopy}
          className="flex gap-2 items-center"
        >
          {copied ? <Check size={16} /> : <Clipboard size={16} />}
          {copied ? "Copied" : "Copy JSON"}
        </Button>

        <Button
          size="sm"
          variant="outline"
          onClick={handleDownload}
          className="flex gap-2 items-center"
        >
          {downloading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : downloaded ? (
            <Check size={16} className="text-green-500" />
          ) : (
            <Download size={16} />
          )}
          {downloading
            ? "Downloading..."
            : downloaded
            ? "Downloaded"
            : "Download JSON"}
        </Button>
      </div>

      <ScrollArea className="max-h-[400px] w-full overflow-y-auto">
        <pre className="whitespace-pre-wrap break-words text-sm bg-white text-black p-3 rounded-md">
          <CollapsibleJSON value={jsonData} expanded={true} />
        </pre>
      </ScrollArea>
    </Card>
  );
}