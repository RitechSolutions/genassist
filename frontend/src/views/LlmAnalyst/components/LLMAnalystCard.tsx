import { Card } from "@/components/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Edit, Trash, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";

interface LLMAnalystCardProps {
  analysts: LLMAnalyst[];
  searchQuery: string;
  onEdit: (analyst: LLMAnalyst) => void;
  onDelete: (id: string) => void;
}

export function LLMAnalystCard({ analysts, searchQuery, onEdit, onDelete }: LLMAnalystCardProps) {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 2000);
    return () => clearTimeout(timeout);
  }, [analysts]);

  const filtered = analysts.filter(a => {
    const name = a.name?.toLowerCase() || "";
    const provider = a.llm_provider?.name?.toLowerCase() || "";
    return name.includes(searchQuery.toLowerCase()) || provider.includes(searchQuery.toLowerCase());
  });

  if (loading) {
    return (
      <Card className="p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (filtered.length === 0) {
    return (
      <Card className="p-8 text-center text-muted-foreground">
        {searchQuery ? "No LLM Analysts found matching your search" : "No LLM Analysts found"}
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Prompt</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map(analyst => (
            <TableRow key={analyst.id}>
              <TableCell>{analyst.name}</TableCell>
              <TableCell>{analyst.llm_provider?.name}</TableCell>
              <TableCell className="max-w-[300px] truncate">{analyst.prompt}</TableCell>
              <TableCell>
                <Badge variant={analyst.is_active ? "default" : "secondary"}>
                  {analyst.is_active ? "Active" : "Inactive"}
                </Badge>
              </TableCell>
              <TableCell className="flex items-center">
                <Button variant="ghost" size="sm" onClick={() => onEdit(analyst)} title="Edit">
                  <Edit className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => onDelete(analyst.id)} title="Delete">
                  <Trash className="w-4 h-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
