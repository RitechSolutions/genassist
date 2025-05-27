import { useEffect, useState } from "react";
import { Card } from "@/components/card";
import { Edit, Loader2, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { formatDate } from "@/helpers/utils";
import { FeatureFlag } from "@/interfaces/featureFlag.interface";
import { toast } from "react-hot-toast";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";
import { 
  getFeatureFlags, 
  deleteFeatureFlag,
  updateFeatureFlag
} from "@/services/featureFlags";
import { Badge } from "@/components/badge";

interface FeatureFlagsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditFeatureFlag: (featureFlag: FeatureFlag) => void;
}

export function FeatureFlagsCard({ 
  searchQuery, 
  refreshKey = 0, 
  onEditFeatureFlag 
}: FeatureFlagsCardProps) {
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [featureFlagToDelete, setFeatureFlagToDelete] = useState<FeatureFlag | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchFeatureFlags();
  }, [refreshKey]);

  const fetchFeatureFlags = async () => {
    try {
      setLoading(true);
      const data = await getFeatureFlags();
      setFeatureFlags(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch feature flags");
      toast.error("Failed to fetch feature flags");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (featureFlag: FeatureFlag) => {
    setFeatureFlagToDelete(featureFlag);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!featureFlagToDelete?.id) return;
    
    try {
      setIsDeleting(true);
      await deleteFeatureFlag(featureFlagToDelete.id);
      toast.success("Feature flag deleted successfully");
      fetchFeatureFlags();
    } catch (error) {
      toast.error("Failed to delete feature flag");
      console.error("Error deleting feature flag:", error);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setFeatureFlagToDelete(null);
    }
  };

  const handleToggleActive = async (flag: FeatureFlag) => {
    if (!flag.id) return;
    
    try {
      await updateFeatureFlag(flag.id, {
        ...flag,
        is_active: flag.is_active === 1 ? 0 : 1,
      });
      toast.success(`Feature flag ${flag.is_active === 1 ? 'deactivated' : 'activated'}`);
      fetchFeatureFlags();
    } catch (error) {
      toast.error("Failed to update feature flag status");
      console.error("Error updating feature flag:", error);
    }
  };

  const filteredFeatureFlags = featureFlags.filter((flag) =>
    flag.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
    flag.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    flag.val.toLowerCase().includes(searchQuery.toLowerCase())
  );

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

  if (filteredFeatureFlags.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No feature flags found matching your search" : "No feature flags found"}
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredFeatureFlags.map((flag) => (
              <TableRow key={flag.id}>
                <TableCell className="font-medium">{flag.key}</TableCell>
                <TableCell>{flag.val}</TableCell>
                <TableCell className="max-w-md truncate">
                  {flag.description || "-"}
                </TableCell>
                <TableCell>
                  <Badge variant={flag.is_active === 1 ? "default" : "secondary"}>
                    {flag.is_active === 1 ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditFeatureFlag(flag)}
                      title="Edit Feature Flag"
                    >
                      <Edit className="w-4 h-4 text-black" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(flag)}
                      title="Delete Feature Flag"
                    >
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the feature flag
              "{featureFlagToDelete?.key}".
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
} 