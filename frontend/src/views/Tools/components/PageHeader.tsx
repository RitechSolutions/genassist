import { FC } from "react";
import { Button } from "@/components/button";
import { ArrowLeft } from "lucide-react";

interface PageHeaderProps {
  title: string;
  onBack: () => void;
}

export const PageHeader: FC<PageHeaderProps> = ({ title, onBack }) => (
  <div className="flex items-center space-x-4 mb-6 px-6">
    <Button
      variant="ghost"
      size="icon"
      className="p-2 rounded-full border border-[#E4E4E7] bg-white"
      onClick={onBack}
    >
      <ArrowLeft className="w-8 h-8 text-gray-600" />
    </Button>
    <h1 className="text-2xl font-semibold">{title}</h1>
  </div>
);
