import { InfoIcon } from "lucide-react";

interface CardHeaderProps {
  title: string;
  tooltipText?: string;
  linkText?: string;
  linkHref?: string;
}

export function CardHeader({ title, tooltipText, linkText, linkHref }: CardHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        {tooltipText && (
          <div className="relative group">
            <InfoIcon className="w-4 h-4 text-gray-400 cursor-help" />
            <div className="absolute z-10 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg">
              {tooltipText}
              <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-800"></div>
            </div>
          </div>
        )}
      </div>
      {linkText && linkHref && (
        <a href={linkHref} className="text-sm text-primary hover:underline">
          {linkText}
        </a>
      )}
    </div>
  );
} 