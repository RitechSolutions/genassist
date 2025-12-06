import React, { useState } from "react";
import { Label } from "@/components/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CSVAnalysisResult } from "@/services/mlModels";

interface CSVAnalysisDisplayProps {
  analysisResult: CSVAnalysisResult;
}

export const CSVAnalysisDisplay: React.FC<CSVAnalysisDisplayProps> = ({
  analysisResult,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="space-y-2">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded border cursor-pointer hover:bg-gray-100 transition-colors flex items-center justify-between">
            <p>
              <strong>{analysisResult.row_count}</strong> rows,{" "}
              <strong>{analysisResult.column_count}</strong> columns
              {analysisResult.column_names.length > 0 && (
                <>: {analysisResult.column_names.slice(0, 5).join(", ")}
                {analysisResult.column_names.length > 5 && "..."}</>
              )}
            </p>
            {analysisResult.sample_data &&
              analysisResult.sample_data.length > 0 && (
                <div className="ml-2">
                  {isOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </div>
              )}
          </div>
        </CollapsibleTrigger>
        {analysisResult.sample_data && analysisResult.sample_data.length > 0 && (
          <CollapsibleContent>
            <div className="border rounded-lg overflow-hidden mt-2">
              <div className="bg-gray-50 px-3 py-2 border-b">
                <Label className="text-sm font-medium">Sample Data</Label>
              </div>
              <div className="max-h-64 overflow-auto">
                <Table className="min-w-full">
                  <TableHeader className="sticky top-0 bg-white z-10">
                    <TableRow>
                      {analysisResult.column_names.map((columnName) => (
                        <TableHead
                          key={columnName}
                          className="text-xs font-medium bg-gray-50"
                        >
                          {columnName}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {analysisResult.sample_data.map((row, rowIndex) => (
                      <TableRow key={rowIndex}>
                        {analysisResult.column_names.map((columnName) => (
                          <TableCell key={columnName} className="text-xs">
                            {row[columnName] !== null &&
                            row[columnName] !== undefined
                              ? String(row[columnName])
                              : (
                                  <span className="text-gray-400 italic">
                                    null
                                  </span>
                                )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </CollapsibleContent>
        )}
      </Collapsible>
    </div>
  );
};

