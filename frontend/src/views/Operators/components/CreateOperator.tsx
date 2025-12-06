import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Label } from "@/components/label";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { toast } from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";
import { createOperator } from "@/services/operators";
import { Operator } from "@/interfaces/operator.interface";

type NewOperatorResponse = Operator & {
  user: { password?: string };
};

type NewOperatorResponse = Operator & {
  user: { password?: string };
};

interface CreateOperatorProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onOperatorCreated: (newOperator: NewOperatorResponse) => void;
}

function buildNewOperator(firstName: string, lastName: string, email: string) {
  return {
    firstName,
    lastName,
    avatar: "",
    user: {
      email,
    },
    operator_statistics: {
      positive: 100,
      neutral: 100,
      negative: 100,
      totalCallDuration: "00:00:01",
      score: 0,
      callCount: 0,
      avg_customer_satisfaction: 0,
      avg_resolution_rate: 0,
      avg_response_time: 0,
      avg_quality_of_service: 0,
      id: uuidv4(),
    },
  };
}

export function CreateOperator({
  isOpen,
  onOpenChange,
  onOperatorCreated,
}: CreateOperatorProps) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFirstName("");
      setLastName("");
      setEmail("");
      setIsSubmitting(false);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "First Name", isEmpty: !firstName },
      { label: "Last Name", isEmpty: !lastName },
      { label: "Email", isEmpty: !email },
    ];

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label);

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    const newOperator = buildNewOperator(firstName, lastName, email);
    setIsSubmitting(true);

    try {
      const createdOperator = await createOperator(newOperator);
      if (createdOperator) {
        toast.success("Operator created successfully.");

        onOperatorCreated(createdOperator as NewOperatorResponse);
        onOpenChange(false);
      } else {
        toast.error("Failed to create operator.");
      }
    } catch {
      toast.error("Failed to create operator.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Operator + User</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>First Name</Label>
            <Input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
          </div>
          <div>
            <Label>Last Name</Label>
            <Input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </div>
          <div>
            <Label>Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create Operator"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
