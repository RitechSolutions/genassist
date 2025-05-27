import { Card } from "@/components/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { useState } from "react";
import { Edit, Trash, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { DataSource } from "@/interfaces/dataSource.interface";

interface DataSourceCardProps {
  dataSources: DataSource[];
  searchQuery: string;
  refreshKey: number;
  onEditDataSource?: (dataSource: DataSource) => void;
  onDeleteDataSource?: (id: string) => void;
}

export function DataSourceCard({
  searchQuery,
  dataSources, 
  onEditDataSource,
  onDeleteDataSource,
}: DataSourceCardProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredDataSources = dataSources.filter((dataSource) => {
    const name = dataSource.name?.toLowerCase() || ''; 
    const sourceType = dataSource.source_type?.toLowerCase() || ''; 
  
    return name.includes(searchQuery.toLowerCase()) || sourceType.includes(searchQuery.toLowerCase());
  });

  if (loading) {
    return (
      <Card className="p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-red-500">{error}</div>
      </Card>
    );
  }

  if (filteredDataSources.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No data sources found matching your search" : "No data sources found"}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Source Type</TableHead>
            <TableHead className="w-[150px]">Connection Data</TableHead>
            <TableHead className="text-center">Status</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredDataSources.map((dataSource) => (
            <TableRow key={dataSource.id}>
              <TableCell className="font-medium">{dataSource.name}</TableCell>
              <TableCell>{dataSource.source_type}</TableCell>
              <TableCell className="max-w-[150px]">{dataSource.connection_data}</TableCell>
              <TableCell className="text-center">
                <Badge variant={dataSource.is_active ? "default" : "secondary"}>
                  {dataSource.is_active ? "Active" : "Inactive"}
                </Badge>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEditDataSource(dataSource)}
                  title="Edit Data Source"
                >
                  <Edit className="w-4 h-4 text-black" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  title="Delete Data Source"
                  onClick={() => onDeleteDataSource?.(dataSource.id!)}
                >
                  <Trash className="w-4 h-4 text-black" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}