import React from "react";
import { Label } from "@/components/label";

import { ParameterBadges } from "../components/custom/ParameterSection";

export interface NodeContentRow {
  label: string;
  value: any;
  placeholder?: string;
  isSelection?: boolean;
  isTextArea?: boolean;
  isCode?: boolean;
  areDynamicVars?: boolean;
}

interface NodeContentProps {
  data: NodeContentRow[];
}

const simplifyParamNames = (params) => {
  return Object.entries(params).reduce((acc, [key, value]) => {
    const prefix = "direct_input.parameters.";
    const newKey = key.startsWith(prefix) ? key.replace(prefix, "") : key;
    acc[newKey] = value;
    return acc;
  }, {});
};

const replaceSessionVars = (params) => {
  const result = {};
  let count = 0;
  let value = null;

  Object.entries(params).forEach(([key, value]) => {
    if (key.startsWith("session.")) {
      count += 1;
      value = value;
    } else {
      result[key] = value;
    }
  });

  if (count > 0) {
    const key =
      count === 1 ? "1 session variable" : `${count} session variables`;
    result[key] = value;
  }

  return result;
};

const transformParams = (params) => {
  return replaceSessionVars(simplifyParamNames(params));
};

export const NodeContent: React.FC<NodeContentProps> = ({ data }) => {
  const renderRow = (row) => {
    if (row.areDynamicVars) {
      if (
        row.value &&
        Object.keys(row.value).length > 0 &&
        !Object.keys(row.value).includes("direct_input")
      ) {
        return <ParameterBadges params={transformParams(row.value)} />;
      } else {
        return (
          <div className="text-sm text-accent-foreground italic">
            {"None used"}
          </div>
        );
      }
    }

    if (!row.value) {
      return (
        <div className="text-sm text-accent-foreground italic">
          {row.placeholder || "None provided"}
        </div>
      );
    }

    if (row.isTextArea || row.isCode) {
      const maxLines = data.length === 1 ? 6 : data.length === 2 ? 3 : 1;
      const noEmptyLines = row.value
        .split("\n")
        .filter((line: string) => line.trim() !== "")
        .join("\n");
      return (
        <div
          className="px-2 py-1 text-accent-foreground bg-zinc-100 rounded-sm overflow-hidden"
          style={{
            display: "-webkit-box",
            WebkitLineClamp: maxLines,
            WebkitBoxOrient: "vertical",
            whiteSpace: "pre-wrap",
          }}
        >
          <div className={row.isCode ? "font-mono" : ""}>{noEmptyLines}</div>
        </div>
      );
    }

    if (row.isSelection) {
      row.value = row.value.replace(/_/g, " ");
      row.value =
        row.value.charAt(0).toUpperCase() + row.value.slice(1).toLowerCase();
    }

    return (
      <div
        className={"text-sm text-accent-foreground truncate max-w-full"}
        title={row.value}
      >
        {row.value}
      </div>
    );
  };

  return (
    <div className="p-4 mx-0.5 mb-0.5 bg-white rounded-sm">
      <div className="space-y-4">
        {data.map((row, index) => {
          return (
            <div key={index} className="space-y-0">
              <Label className="text-muted-foreground font-semibold">
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
