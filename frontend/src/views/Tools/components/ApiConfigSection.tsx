import { FC } from "react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { Input } from "@/components/input";
import { ToolSection } from "../components/ToolSection"; 

interface ApiConfigSectionProps {
  endpoint: string;
  setEndpoint: (v: string) => void;
  method: string;
  setMethod: (v: string) => void;
  headers: any[];
  setHeaders: React.Dispatch<React.SetStateAction<any[]>>;
  queryParams: any[];
  setQueryParams: React.Dispatch<React.SetStateAction<any[]>>;
  bodyParams: any[];
  setBodyParams: React.Dispatch<React.SetStateAction<any[]>>;
  headersTab: string;
  setHeadersTab: (v: string) => void;
  queryTab: string;
  setQueryTab: (v: string) => void;
  bodyTab: string;
  setBodyTab: (v: string) => void;
  addItem: (setter: any, sample: any) => void;
  removeItem: (setter: any, id: string) => void;
}

export const ApiConfigSection: FC<ApiConfigSectionProps> = ({
  endpoint,
  setEndpoint,
  method,
  setMethod,
  headers,
  setHeaders,
  queryParams,
  setQueryParams,
  bodyParams,
  setBodyParams,
  headersTab,
  setHeadersTab,
  queryTab,
  setQueryTab,
  bodyTab,
  setBodyTab,
  addItem,
  removeItem,
}) => (
  <div className="grid md:grid-cols-3 gap-6">
    <div className="hidden md:block">
      <h2 className="text-lg font-medium">API Configuration</h2>
      <p className="text-sm text-muted-foreground mt-1">
        Configure the API endpoint and parameters
      </p>
    </div>
    <div className="col-span-2 space-y-6">
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Method</label>
          <Select value={method} onValueChange={setMethod}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["GET", "POST", "PUT", "DELETE"].map(m => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="col-span-2 flex flex-col gap-2">
          <label className="text-sm font-medium">Endpoint URL</label>
          <Input
            placeholder="https://api.example.com/endpoint"
            value={endpoint}
            onChange={e => setEndpoint(e.target.value)}
          />
        </div>
      </div>

      <ToolSection
        title="Headers"
        subtitle="Define the headers for your API request"
        items={headers}
        setItems={setHeaders}
        tab={headersTab}
        setTab={setHeadersTab}
        addItem={addItem}
        removeItem={removeItem}
        sample={{ name: "", value: "" }}
      />
      <ToolSection
        title="Query Parameters"
        subtitle="Define query parameters for your API request"
        items={queryParams}
        setItems={setQueryParams}
        tab={queryTab}
        setTab={setQueryTab}
        addItem={addItem}
        removeItem={removeItem}
        sample={{ name: "", value: "" }}
      />
      <ToolSection
        title="Request Body"
        subtitle="Define the body content for your API request"
        items={bodyParams}
        setItems={setBodyParams}
        tab={bodyTab}
        setTab={setBodyTab}
        addItem={addItem}
        removeItem={removeItem}
        sample={{ name: "", value: "" }}
      />
    </div>
  </div>
);
