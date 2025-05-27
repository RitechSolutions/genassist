import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { getApiKeys, createApiKey, updateApiKey, revokeApiKey } from "@/services/apiKeys";
import ApiKeyForm from "./ApiKeyForm";
import { ApiKey } from "@/interfaces/api-key.interface";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/alert-dialog";
import { PlusCircle, Edit, Trash2 } from "lucide-react";
import { Badge } from "@/components/badge";

interface Props {
  agentId: string;
  userId: string;
  isOpen: boolean;
  onClose(): void;
}

export default function ManageApiKeysModal({ agentId, userId, isOpen, onClose }: Props) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [editing, setEditing] = useState<ApiKey | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  async function load() {
    const data = await getApiKeys(userId);
    setKeys(data);
  }

  useEffect(() => {
    if (isOpen) load();
  }, [isOpen, userId]);

  async function handleSave(saved: ApiKey) {
    setKeys(k => editing
      ? k.map(x => x.id===saved.id ? saved : x)
      : [...k, saved]
    );
    setFormOpen(false);
    setEditing(null);
  }

  async function handleDelete(keyId: string) {
    await revokeApiKey(keyId);
    await load();
  }

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold">Manage API Keys</DialogTitle>
          </DialogHeader>
          
          <div className="flex justify-end mb-4">
            <Button 
              onClick={()=>{ setEditing(null); setFormOpen(true); }}
              className="flex items-center gap-2"
            >
              <PlusCircle className="h-4 w-4" />
              Add API Key
            </Button>
          </div>
          
          {keys.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <p>No API keys found</p>
              <p className="text-sm">Create one to get started</p>
            </div>
          ) : (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-left">Status</TableHead>
                    <TableHead className="text-center">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {keys.map(k => (
                    <TableRow key={k.id}>
                      <TableCell className="font-medium">{k.name}</TableCell>
                                     <TableCell>
                  <Badge variant={k.is_active === 1 ? "default" : "secondary"}>
                    {k.is_active === 1 ? "Active" : "Revoked"}
                  </Badge>
                </TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button
                        variant="ghost"
                          size="sm"
                          onClick={()=>{ setEditing(k); setFormOpen(true); }}
                          className="h-8 px-2 inline-flex items-center"
                        >
                          <Edit className="h-4 w-4 mr-1" />
                        </Button>
                        
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                              <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2 inline-flex items-center"
                            >
                              <Trash2 className="h-4 w-4 mr-1 text-red-600" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete API Key</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete this API key? This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDelete(k.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ApiKeyForm
        agentId={agentId}
        userId={userId}
        existingKey={editing ?? undefined}
        open={formOpen}
        onClose={()=>setFormOpen(false)}
        onSaved={handleSave}
      />
    </>
  );
}
