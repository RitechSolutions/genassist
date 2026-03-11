import { useEffect, useState } from "react";
import { Card } from "@/components/card";
import { Pencil, Loader2, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Language } from "@/interfaces/translation.interface";
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
import { getAllLanguages, updateLanguage, deleteLanguage } from "@/services/translations";
import { Badge } from "@/components/badge";

interface LanguagesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditLanguage: (language: Language) => void;
}

export function LanguagesCard({
  searchQuery,
  refreshKey = 0,
  onEditLanguage,
}: LanguagesCardProps) {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [languageToDelete, setLanguageToDelete] = useState<Language | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchLanguages();
  }, [refreshKey]);

  const fetchLanguages = async () => {
    try {
      setLoading(true);
      const data = await getAllLanguages();
      setLanguages(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch languages");
      toast.error("Failed to fetch languages.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (language: Language) => {
    setLanguageToDelete(language);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!languageToDelete?.id) return;

    try {
      setIsDeleting(true);
      await deleteLanguage(languageToDelete.id);
      toast.success("Language deleted successfully.");
      fetchLanguages();
    } catch {
      toast.error("Failed to delete language.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setLanguageToDelete(null);
    }
  };

  const handleToggleActive = async (language: Language) => {
    if (!language.id) return;

    try {
      await updateLanguage(language.id, { is_active: !language.is_active });
      toast.success(
        `Language ${language.is_active ? "deactivated" : "activated"} successfully.`
      );
      fetchLanguages();
    } catch {
      toast.error("Failed to update language status.");
    }
  };

  const filteredLanguages = languages.filter(
    (lang) =>
      lang.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lang.name.toLowerCase().includes(searchQuery.toLowerCase())
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

  if (filteredLanguages.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery
            ? "No languages found matching your search"
            : "No languages found"}
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
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredLanguages.map((language) => (
              <TableRow key={language.id}>
                <TableCell className="font-medium">{language.code}</TableCell>
                <TableCell>{language.name}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={language.is_active}
                      onCheckedChange={() => handleToggleActive(language)}
                    />
                    <Badge variant={language.is_active ? "default" : "secondary"}>
                      {language.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditLanguage(language)}
                      title="Edit Language"
                    >
                      <Pencil className="w-4 h-4 text-black" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(language)}
                      title="Delete Language"
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

      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the
              language "{languageToDelete?.name}" ({languageToDelete?.code}).
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
