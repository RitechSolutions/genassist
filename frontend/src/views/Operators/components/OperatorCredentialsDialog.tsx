import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/dialog";
import { Label } from "@/components/label";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { SecretInput } from "@/components/SecretInput";

interface OperatorCredentials {
  username: string;
  email: string;
  password: string;
}

interface OperatorCredentialsDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  credentials: OperatorCredentials | null;
}

export function OperatorCredentialsDialog({ isOpen, onOpenChange, credentials }: OperatorCredentialsDialogProps) {
  if (!credentials) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Operator Created Successfully</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Please save the following credentials. The password is a one-time password and will not be shown again.
          </p>
          <div>
            <Label>Username</Label>
            <Input value={credentials.username} readOnly />
          </div>
          <div>
            <Label>Email</Label>
            <Input type="email" value={credentials.email} readOnly />
          </div>
          <div>
            <Label>Password</Label>
            <SecretInput value={credentials.password} />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 