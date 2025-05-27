import { useState, useEffect } from "react";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-hot-toast";
import {
  createTool,
  updateTool,
  getToolById,
  testPythonCode,
  testPythonCodeWithSchema,
  generatePythonTemplate,
} from "@/services/tools";
import { Tool } from "@/interfaces/tool.interface";

import { CirclePlay } from "lucide-react";
import { Card, CardContent } from "@/components/card";

import { PageHeader } from "./../components/PageHeader";
import { BasicInfo } from "../components/BasicInfo";
import { ParameterSection, Param } from "../components/ParameterSection";
import { ApiConfigSection } from "../components/ApiConfigSection";
import { FunctionConfigSection } from "../components/FunctionConfigSection";
import { SubmitButtons } from "../components/SubmitButtons";
import { v4 as uuidv4 } from 'uuid';

export default function CreateTool() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const isEditMode = Boolean(id);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [toolType, setToolType] = useState<"api" | "function">("api");
  const [endpoint, setEndpoint] = useState("");
  const [method, setMethod] = useState("GET");
  const [headers, setHeaders] = useState<any[]>([
    { id: uuidv4(), name: "", value: "" },
  ]);
  const [queryParams, setQueryParams] = useState<any[]>([
    { id: uuidv4(), name: "", value: "" },
  ]);
  const [bodyParams, setBodyParams] = useState<any[]>([
    { id: uuidv4(), name: "", value: "" },
  ]);
  const [headersTab, setHeadersTab] = useState("form");
  const [queryTab, setQueryTab] = useState("form");
  const [bodyTab, setBodyTab] = useState("form");

  const [dynamicParams, setDynamicParams] = useState<Param[]>([
    { id: uuidv4(), name: "", type: "String", defaultValue: "", description: "" },
  ]);

  const [code, setCode] = useState<string>(
    `# Python code here\n\nresult = None`
  );
  const [testParameters, setTestParameters] = useState<string>("{}");
  const [testingCode, setTestingCode] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const addItem = (setter, template) =>
    setter(prev => [...prev, { ...template, id: uuidv4() }]);
  const removeItem = (setter, id: string) =>
    setter((prev) => prev.filter((item) => item.id !== id));

  useEffect(() => {
    if (isEditMode && id) {
      setLoading(true);
      getToolById(id)
        .then((t: Tool) => {
          setName(t.name);
          setDescription(t.description);
          setToolType(t.type as "api" | "function");

          if (t.api_config) {
            setEndpoint(t.api_config.endpoint || "");
            setMethod(t.api_config.method || "GET");
            setHeaders(
              Object.entries(t.api_config.headers || {}).map(
                ([key, value]) => ({
                  id: uuidv4(),
                  name: key,
                  value: value as string,
                })
              )
            );
            setQueryParams(
              Object.entries(t.api_config.query_params || {}).map(
                ([key, value]) => ({
                  id: uuidv4(),
                  name: key,
                  value: value as string,
                })
              )
            );
            setBodyParams(
              Object.entries(t.api_config.body || {}).map(([key, value]) => ({
                id: uuidv4(),
                name: key,
                value: value as string,
              }))
            );
          }

          if (t.function_config) {
            setCode(t.function_config.code || "");
          }

          const params = t.parameters_schema
            ? Object.entries(t.parameters_schema).map(
                ([paramName, paramData]: [string, any]) => ({
                  id: uuidv4(),
                  name: paramName,
                  type:
                    (paramData?.type || "String").charAt(0).toUpperCase() +
                    (paramData?.type?.slice(1) || ""),
                  defaultValue: paramData?.default || "",
                  description: paramData?.description || "",
                })
              )
            : [];
          setDynamicParams(
            params.length
              ? params
              : [
                  {
                    id: uuidv4(),
                    name: "",
                    type: "String",
                    defaultValue: "",
                    description: "",
                  },
                ]
          );
        })
        .catch(() => toast.error("Failed to load tool"))
        .finally(() => setLoading(false));
    }
  }, [isEditMode, id]);

  const handleGenerateTemplate = async () => {
    try {
      setLoading(true);
      setError(null);

      const properties: Record<string, any> = {};
      dynamicParams.forEach((p) => {
        if (p.name) {
          properties[p.name] = {
            type: p.type.toLowerCase(),
            default: p.defaultValue,
            description: p.description,
          };
        }
      });

      const parameters_schema = { type: "object", properties };
      const result = await generatePythonTemplate(parameters_schema);

      if (result && typeof result === "object" && "template" in result) {
        setCode(result.template as string);
        setSuccess("Template generated successfully");
      } else {
        setCode(
          "# Failed to generate template: backend response missing 'template'"
        );
        setError(
          "Failed to generate template: Backend did not return 'template'"
        );
      }
    } catch (err: any) {
      setError(
        `Failed to generate template: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTestCode = async () => {
    try {
      setError(null);
      setTestResult(null);
      setTestingCode(true);

      let params = {};
      try {
        params = JSON.parse(testParameters);
      } catch {
        throw new Error("Invalid JSON in test parameters");
      }

      const schema: Record<string, any> = {};
      dynamicParams.forEach((p) => {
        if (p.name) {
          schema[p.name] = {
            type: p.type.toLowerCase(),
            default: p.defaultValue,
            description: p.description,
          };
        }
      });

      let res: any;
      if (Object.keys(schema).length) {
        res = await testPythonCodeWithSchema(code, params, schema);
      } else {
        res = await testPythonCode(code, params);
      }

      const pieces = [`Result: ${JSON.stringify(res.result, null, 2)}`];
      if (res.original_params) {
        pieces.push(
          `\n\nOriginal: ${JSON.stringify(res.original_params, null, 2)}`
        );
      }
      if (res.validated_params) {
        pieces.push(
          `\n\nValidated: ${JSON.stringify(res.validated_params, null, 2)}`
        );
      }
      setTestResult(pieces.join(""));
      setSuccess("Code tested successfully");
    } catch (err: any) {
      setError(err.message || "Test failed");
    } finally {
      setTestingCode(false);
    }
  };

  const handleSubmit = async () => {
    if (!name) {
      toast.error("Please enter a name for the tool");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const parameters_schema: Record<string, any> = {};
      dynamicParams.forEach((p) => {
        if (p.name) {
          parameters_schema[p.name] = {
            type: p.type.toLowerCase(),
            default: p.defaultValue,
            description: p.description,
          };
        }
      });

      const headersRecord: Record<string, any> = {};
      const queryParamsRecord: Record<string, any> = {};
      const bodyRecord: Record<string, any> = {};
      headers.forEach((h) => h.name && (headersRecord[h.name] = h.value));
      queryParams.forEach(
        (q) => q.name && (queryParamsRecord[q.name] = q.value)
      );
      bodyParams.forEach((b) => b.name && (bodyRecord[b.name] = b.value));

      const payload = {
        ...(isEditMode && id ? { id } : {}),
        name,
        description,
        type: toolType,
        api_config: {
          endpoint: toolType === "api" ? endpoint : "",
          method: toolType === "api" ? method : "GET",
          headers: headersRecord,
          query_params: queryParamsRecord,
          body: bodyRecord,
        },
        function_config: {
          code: toolType === "function" ? code : "",
        },
        parameters_schema,
      } as Partial<Tool>;

      if (isEditMode && id) {
        await updateTool(id, payload);
        toast.success("Tool updated successfully");
      } else {
        await createTool(payload);
        toast.success("Tool created successfully");
      }
      navigate("/tools");
    } catch (err: any) {
      console.error("Submit error:", err);
      setError(err.message || "Failed to save tool");
      toast.error("Failed to save tool");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <SidebarProvider>
        <div className="min-h-screen flex w-full">
          {!isMobile && <AppSidebar />}
          <main className="flex-1 flex items-center justify-center">
            <CirclePlay className="animate-spin w-12 h-12" />
          </main>
        </div>
      </SidebarProvider>
    );
  }

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 bg-zinc-50 py-8">
          <div className="max-w-[1140px] mx-auto">
            <PageHeader
              title={isEditMode ? "Edit Tool" : "Create New Tool"}
              onBack={() => navigate(-1)}
            />

            <Card className="mx-6 rounded-lg">
              <CardContent className="p-6 space-y-8">
                <BasicInfo
                  name={name}
                  onNameChange={setName}
                  description={description}
                  onDescriptionChange={(val: string) => {
                    if (val.length > 255) {
                      toast.error("Description cannot exceed 255 characters");
                    }
                    setDescription(val.slice(0, 255));
                  }}                  
                  toolType={toolType}
                  onToolTypeChange={setToolType}
                />

                <div className="-mx-6 my-6 border-t border-gray-200" />

                <ParameterSection
                  dynamicParams={dynamicParams}
                  setDynamicParams={setDynamicParams}
                  addItem={addItem}
                  removeItem={removeItem}
                />

                <div className="-mx-6 my-6 border-t border-gray-200" />

                {toolType === "api" ? (
                  <ApiConfigSection
                    endpoint={endpoint}
                    setEndpoint={setEndpoint}
                    method={method}
                    setMethod={setMethod}
                    headers={headers}
                    setHeaders={setHeaders}
                    queryParams={queryParams}
                    setQueryParams={setQueryParams}
                    bodyParams={bodyParams}
                    setBodyParams={setBodyParams}
                    headersTab={headersTab}
                    setHeadersTab={setHeadersTab}
                    queryTab={queryTab}
                    setQueryTab={setQueryTab}
                    bodyTab={bodyTab}
                    setBodyTab={setBodyTab}
                    addItem={addItem}
                    removeItem={removeItem}
                  />
                ) : (
                  <FunctionConfigSection
                    code={code}
                    onCodeChange={setCode}
                    handleGenerateTemplate={handleGenerateTemplate}
                    dynamicParams={dynamicParams}
                    testParameters={testParameters}
                    onTestParametersChange={setTestParameters}
                    testingCode={testingCode}
                    handleTestCode={handleTestCode}
                    error={error}
                    success={success}
                    testResult={testResult}
                  />
                )}

                <div className="-mx-6 my-6 border-t border-gray-200" />

                <SubmitButtons
                  onCancel={() => navigate("/tools")}
                  onSubmit={handleSubmit}
                  submitting={submitting}
                  isEditMode={isEditMode}
                />
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
