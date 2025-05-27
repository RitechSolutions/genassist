import { FC } from "react";
import { Button } from "@/components/button";
import { Trash2, Plus } from "lucide-react";
import { Input } from "@/components/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";

export interface Param {
  id: string;
  name: string;
  type: string;
  defaultValue: string;
  description: string;
}

interface ParameterSectionProps {
  dynamicParams: Param[];
  setDynamicParams: React.Dispatch<React.SetStateAction<Param[]>>;
  addItem: (
    setter: React.Dispatch<React.SetStateAction<Param[]>>,
    template: Omit<Param, "id">
  ) => void;
  removeItem: (
    setter: React.Dispatch<React.SetStateAction<Param[]>>,
    id: string
  ) => void;
}

export const ParameterSection: FC<ParameterSectionProps> = ({
  dynamicParams,
  setDynamicParams,
  addItem,
  removeItem,
}) => (
  <div className="grid md:grid-cols-3 gap-6">
    <div className="hidden md:block">
      <h2 className="text-lg font-medium">Dynamic Parameters Schema</h2>
      <p className="text-sm text-muted-foreground mt-1">
        Define the input schema for your tool
      </p>
    </div>
    <div className="col-span-2 space-y-4">
      {dynamicParams.map(param => (
        <div key={param.id} className="flex items-center gap-4">
          <div className="flex-1 space-y-4">
            {/* Name + Type */}
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Parameter Name</label>
                <Input
                  placeholder="param_1"
                  value={param.name}
                  onChange={e =>
                    setDynamicParams(prev =>
                      prev.map(x =>
                        x.id === param.id ? { ...x, name: e.target.value } : x
                      )
                    )
                  }
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Type</label>
                <Select
                  value={param.type}
                  onValueChange={v =>
                    setDynamicParams(prev =>
                      prev.map(x => (x.id === param.id ? { ...x, type: v } : x))
                    )
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["String", "Number", "Boolean", "Object", "Array"].map(t => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {/* Default + Description */}
            <div className="grid grid-cols-2 gap-4 border-b border-gray-200 pb-8">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Default Value</label>
                <Input
                  placeholder="Enter default value"
                  value={param.defaultValue}
                  onChange={e =>
                    setDynamicParams(prev =>
                      prev.map(x =>
                        x.id === param.id ? { ...x, defaultValue: e.target.value } : x
                      )
                    )
                  }
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Description</label>
                <Input
                  placeholder="Parameter description"
                  value={param.description}
                  onChange={e =>
                    setDynamicParams(prev =>
                      prev.map(x =>
                        x.id === param.id ? { ...x, description: e.target.value } : x
                      )
                    )
                  }
                />
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-red-500 p-2 self-center"
            onClick={() => removeItem(setDynamicParams, param.id)}
            disabled={dynamicParams.length <= 1}
          >
            <Trash2 className="w-5 h-5" />
          </Button>
        </div>
      ))}
      <div className="pt-4">
        <Button
          variant="outline"
          size="sm"
          className="h-8 rounded-lg flex items-center gap-2"
          onClick={() =>
            addItem(setDynamicParams, {
              name: "",
              type: "String",
              defaultValue: "",
              description: "",
            })
          }
        >
          <Plus className="w-4 h-4" /> Add Parameter
        </Button>
      </div>
    </div>
  </div>
);
