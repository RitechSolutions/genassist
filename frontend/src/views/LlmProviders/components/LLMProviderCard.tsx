import { Card } from "@/components/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Edit, Loader2, Trash2 } from "lucide-react";
import { LLMProvider } from "@/interfaces/llmProvider.interface";

interface LLMProviderCardProps {
  providers: LLMProvider[];
  searchQuery: string;
  loading: boolean;
  onEdit: (provider: LLMProvider) => void;
  onDelete: (id: string) => void;
}

export function LLMProviderCard({
  providers,
  searchQuery,
  loading,
  onEdit,
  onDelete,
}: LLMProviderCardProps) {
  const filtered = providers.filter((p) => {
    const name = p.name.toLowerCase();
    const type = p.llm_model_provider.toLowerCase();
    const model = p.llm_model.toLowerCase();
    return (
      name.includes(searchQuery.toLowerCase()) ||
      type.includes(searchQuery.toLowerCase()) ||
      model.includes(searchQuery.toLowerCase())
    );
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
        {searchQuery
          ? "No LLM Providers matching your search"
          : "No LLM Providers found"}
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((provider) => (
            <TableRow key={provider.id}>
              <TableCell>{provider.name}</TableCell>
              <TableCell>{provider.llm_model_provider}</TableCell>
              <TableCell>{provider.llm_model}</TableCell>
              <TableCell>
                <Badge variant={provider.is_active ? "default" : "secondary"}>
                  {provider.is_active ? "Active" : "Inactive"}
                </Badge>
              </TableCell>
              <TableCell className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEdit(provider)}
                  title="Edit"
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(provider.id)}
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4 text-red-600" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
