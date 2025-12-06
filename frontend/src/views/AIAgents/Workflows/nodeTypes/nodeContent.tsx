import React from "react";
import { Label } from "@/components/label";

import { ParameterBadges } from "../components/custom/ParameterSection";

interface ParameterBadgesProps {
  params: Record<string, { type: string; required?: boolean }>;
  className?: string;
}

interface NodeContentRow {
  label: string;
  value: string | Record<string, { type: string; required?: boolean }>;
  isMono?: boolean;
  hasMultipleLines?: boolean;
  placeholder?: string;
}

interface NodeContentProps {
  data: NodeContentRow[];
}

const NodeContent: React.FC<NodeContentProps> = ({ data }) => {
  const renderRow = (row) => {
    if (typeof row.value === "string") {
      if (row.value) {
        if (row.hasMultipleLines) {
          if (row.isMono) {
            return (
              <pre className="whitespace-pre-wrap" style={{ color: "#18181B" }}>
                {row.value}
              </pre>
            );
          } else {
            return (
              <p className="whitespace-pre-wrap" style={{ color: "#18181B" }}>
                {row.value}
              </p>
            );
          }
        } else {
          return (
            <div
              className={`text-sm text-gray-600 truncate max-w-full${
                row.isMono ? " font-mono" : ""
              }`}
              style={{ color: "#18181B" }}
              title={row.value} // Show full text on hover
            >
              {row.value}
            </div>
          );
        }
      } else {
        return (
          <div
            className={"text-sm text-gray-400 italic"}
            style={{ color: "#18181B" }}
          >
            {row.placeholder || "No value provided"}
          </div>
        );
      }
    } else {
      if (row.value && Object.keys(row.value).length > 0) {
        return <ParameterBadges params={row.value} />;
      } else {
        return (
          <div
            className={"text-sm text-gray-400 italic"}
            style={{ color: "#18181B" }}
          >
            {row.placeholder || "No value provided"}
          </div>
        );
      }
    }
  };

  return (
    <div className="p-4 mx-1 mb-1 bg-white rounded-md">
      <div className="space-y-4">
        {data.map((row, index) => {
          return (
            <div key={index} className="space-y-0">
              <Label style={{ color: "#71717A", fontWeight: 600 }}>
                {row.label.toUpperCase()}
              </Label>
              {renderRow(row)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default NodeContent;
