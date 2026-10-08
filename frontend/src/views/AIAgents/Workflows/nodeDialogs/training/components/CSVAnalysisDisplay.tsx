import React, { useState } from "react";
import { Label } from "@/components/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CSVAnalysisResult } from "@/services/mlModels";
import {
  getPreviewEdgeItems,
  getPreviewRows,
  PREVIEW_ELLIPSIS,
  type PreviewSource,
} from "../trainDataSourcePreview";

interface CSVAnalysisDisplayProps {
  analysisResult: CSVAnalysisResult;
  source?: PreviewSource;
}

export const CSVAnalysisDisplay: React.FC<CSVAnalysisDisplayProps> = ({
  analysisResult,
  source = "file",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const previewColumns = getPreviewEdgeItems(analysisResult.column_names, 5);
  const previewRows = getPreviewRows(analysisResult.sample_data || [], source);
  const columnsAreLimited = analysisResult.column_names.length > 10;
  const rowsAreLimited = source === "file" && (analysisResult.sample_data?.length || 0) > 4;
  const rowLabel = analysisResult.row_count === 1 ? "row" : "rows";

  return (
    <div className="space-y-2">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded border cursor-pointer hover:bg-muted transition-colors flex items-center justify-between">
            <p>
              {source === "query" && "Showing "}
              <strong>{analysisResult.row_count}</strong>{" "}
              {source === "query" ? `preview ${rowLabel}` : rowLabel},{" "}
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
              <div className="bg-muted px-3 py-2 border-b">
                <Label className="text-sm font-medium">Sample Data</Label>
                {(columnsAreLimited || rowsAreLimited) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {columnsAreLimited && "Showing the first 5 and last 5 columns"}
                    {columnsAreLimited && rowsAreLimited && ", and "}
                    {rowsAreLimited && "the first 2 and last 2 sample rows"}.
                  </p>
                )}
              </div>
              <div className="max-h-64 overflow-auto">
                <Table className="min-w-full">
                  <TableHeader className="sticky top-0 bg-card z-10">
                    <TableRow>
                      {previewColumns.map((columnName) => (
                        columnName === PREVIEW_ELLIPSIS ? (
                          <TableHead
                            key="omitted-columns"
                            aria-label="Omitted columns"
                            className="text-center text-xs font-medium bg-muted"
                          >
                            ...
                          </TableHead>
                        ) : (
                          <TableHead
                            key={columnName}
                            className="text-xs font-medium bg-muted"
                          >
                            {columnName}
                          </TableHead>
                        )
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewRows.map((row, rowIndex) =>
                      row === PREVIEW_ELLIPSIS ? (
                        <TableRow key="omitted-rows">
                          <TableCell
                            colSpan={previewColumns.length}
                            aria-label="Omitted rows"
                            className="text-center text-xs text-muted-foreground"
                          >
                            ...
                          </TableCell>
                        </TableRow>
                      ) : (
                        <TableRow key={rowIndex}>
                          {previewColumns.map((columnName) =>
                            columnName === PREVIEW_ELLIPSIS ? (
                              <TableCell
                                key="omitted-columns"
                                aria-label="Omitted columns"
                                className="text-center text-xs text-muted-foreground"
                              >
                                ...
                              </TableCell>
                            ) : (
                              <TableCell key={columnName} className="text-xs">
                                {row[columnName] !== null &&
                                row[columnName] !== undefined
                                  ? String(row[columnName])
                                  : (
                                      <span className="text-muted-foreground italic">
                                        null
                                      </span>
                                    )}
                              </TableCell>
                            )
                          )}
                        </TableRow>
                      )
                    )}
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
