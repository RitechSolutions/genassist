import { useEffect, useState } from "react";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings, deleteAppSetting } from "@/services/appSettings";
import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { Loader2, Edit, Trash2, Eye, EyeOff } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Button } from "@/components/button";
import { formatDate } from "@/helpers/utils";
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

interface AppSettingsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditSetting: (setting: AppSetting) => void;
}

export function AppSettingsCard({ searchQuery, refreshKey = 0, onEditSetting }: AppSettingsCardProps) {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settingToDelete, setSettingToDelete] = useState<AppSetting | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const settingsData = await getAllAppSettings();
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSetting = async () => {
    if (!settingToDelete) return;
    
    try {
      await deleteAppSetting(settingToDelete.id);
      toast.success("Setting deleted successfully");
      fetchData();
    } catch (err) {
      toast.error("Failed to delete setting");
    } finally {
      setSettingToDelete(null);
      setIsDeleteDialogOpen(false);
    }
  };

  const confirmDelete = (setting: AppSetting) => {
    setSettingToDelete(setting);
    setIsDeleteDialogOpen(true);
  };

  const filteredSettings = settings.filter((setting) =>
    setting.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
    setting.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    setting.value.toLowerCase().includes(searchQuery.toLowerCase())
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

  if (filteredSettings.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No settings found matching your search" : "No settings found"}
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
              <TableHead>Status</TableHead>
              <TableHead>Encrypted</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredSettings.map((setting) => (
              <TableRow key={setting.id}>
                <TableCell className="font-medium">{setting.key}</TableCell>
                <TableCell>
                  <div className="flex items-center">
                    <span className="font-mono text-sm max-w-[200px] truncate">
                      {setting.encrypted === 1 ? "••••••••" : setting.value}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="max-w-[300px]">
                  <span className="line-clamp-2">{setting.description}</span>
                </TableCell>
                <TableCell>
                  <Badge variant={setting.is_active === 1 ? "default" : "secondary"}>
                    {setting.is_active === 1 ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {setting.encrypted === 1 ? (
                    <span className="w-4 h-4 text-gray-500">Yes</span>
                  ) : (
                    <span className="w-4 h-4 text-gray-500">No</span>
                  )}
                </TableCell>
                <TableCell>{setting.created_at ? formatDate(setting.created_at) : 'No date'}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditSetting(setting)}
                      title="Edit Setting"
                    >
                      <Edit className="w-4 h-4 text-black" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => confirmDelete(setting)}
                      title="Delete Setting"
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
              This will permanently delete the setting "{settingToDelete?.key}". This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteSetting} className="bg-red-600 hover:bg-red-700">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
} 