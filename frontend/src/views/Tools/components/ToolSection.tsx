import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/tabs";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Trash2 } from "lucide-react";
import { ToolParameter } from "@/interfaces/tool.interface";
import { v4 as uuidv4 } from "uuid";


interface ToolSectionProps {
  title: string;
  subtitle: string;
  items: ToolParameter[];
  setItems: (items: ToolParameter[]) => void;
  tab: string;
  setTab: (tab: string) => void;
  addItem: (setter: any, sample: any) => void;
  removeItem: (setter: any, id: string) => void;
  sample: { name: string; value: string };
}

export function ToolSection({
  title,
  subtitle,
  items,
  setItems,
  tab,
  setTab,
  addItem,
  removeItem,
  sample,
}: ToolSectionProps) {
  return (
    <div className="space-y-6 pt-2 border-b last:border-b-0 border-gray-200 pb-8">
      <div className="flex justify-between pb-2">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="form">Form View</TabsTrigger>
            <TabsTrigger value="json">JSON Editor</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsContent value="form">
          <div className="space-y-2">
            <div className="flex items-center gap-1 px-1 mt-3">
              <div className="w-2/5 text-sm font-medium">
                Parameter Name
              </div>
              <div className="flex-1 text-sm font-medium">
                Value
              </div>
              <div className="w-8" />
            </div>

            {items.map((item, index) => (
              <div key={item.id} className="flex items-center gap-2">
                <Input
                  placeholder="Enter parameter name"
                  value={item.name}
                  onChange={(e) => {
                    const updated = [...items];
                    updated[index].name = e.target.value;
                    setItems(updated);
                  }}
                  className="w-2/5"
                />
                <Input
                  placeholder="Enter parameter value"
                  value={item.value}
                  onChange={(e) => {
                    const updated = [...items];
                    updated[index].value = e.target.value;
                    setItems(updated);
                  }}
                  className="flex-1"
                />
                <Button
                  size="icon"
                  variant="ghost"
                  className="text-destructive hover:bg-destructive/10"
                  onClick={() => removeItem(setItems, item.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}

            <Button variant="outline" onClick={() => addItem(setItems, sample)}>
              + Add Parameter
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="json">
          <div className="space-y-2">
            <Label className="text-sm font-medium">JSON Body</Label>
            <Textarea
              value={JSON.stringify(items, ["id","name","value"], 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  if (Array.isArray(parsed)) {
                    const updated = parsed.map((item) => ({
                      id: item.id ?? uuidv4(),
                      name: item.name ?? "",
                      value: item.value ?? "",
                    }));
                    
                    setItems(updated);
                  }
                } catch (error) {
                  console.error("Invalid JSON", error);
                }
              }}              
              className="h-60 w-full font-mono text-sm"
              placeholder={`[
                {
                    "name": "parameterName",
                    "value": "parameterValue"
                }
                ]`}
            />
          </div>
        </TabsContent>
      </Tabs>

      <p className="text-xs text-muted-foreground">
        Use <code>@param</code> as a value for dynamic parameters configured in the tool parameters schema.
      </p>
    </div>
  );
}
