import { NodeData } from "../types/nodes";

export interface BaseNodeDialogProps<T extends NodeData, U> {
    isOpen: boolean;
    onClose: () => void;
    data: T;
    onUpdate: (data: U) => void;
    nodeId: string;
    nodeType: string;
  }

  