import { FC } from "react";
import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/mode-json";
import { Button } from "@/components/button";
import { ClipboardList, Maximize2, CodeXml, CirclePlay } from "lucide-react";
import { toast } from "react-hot-toast";

interface FunctionConfigSectionProps {
  code: string;
  onCodeChange: (v: string) => void;
  handleGenerateTemplate: () => Promise<void>;
  dynamicParams: any[];
  testParameters: string;
  onTestParametersChange: (v: string) => void;
  testingCode: boolean;
  handleTestCode: () => Promise<void>;
  error: string | null;
  success: string | null;
  testResult: string | null;
}

export const FunctionConfigSection: FC<FunctionConfigSectionProps> = ({
  code,
  onCodeChange,
  handleGenerateTemplate,
  dynamicParams,
  testParameters,
  onTestParametersChange,
  testingCode,
  handleTestCode,
  error,
  success,
  testResult,
}) => (
  <div className="grid md:grid-cols-3 gap-6 mb-8">
    <div className="hidden md:block">
      <h2 className="text-lg font-medium">Python Function</h2>
      <p className="text-sm text-muted-foreground mt-1">
        Write Python code that will be executed in a sandboxed environment
      </p>
    </div>
    <div className="col-span-2 space-y-4 mb-8">
      <div className="editor-card relative flex flex-col p-6 gap-2.5 h-[648px] bg-[#1C1C1C] backdrop-blur-[20px] rounded-[16px]">
        <div className="editor-controls absolute top-4 right-4 flex gap-2 z-10">
          <button
            className="editor-button flex justify-center items-center p-1 w-[28px] h-[28px] rounded-full hover:bg-white/10"
            onClick={() => {
              navigator.clipboard.writeText(code);
              toast.success("Code copied.");
            }}
          >
            <ClipboardList className="w-5 h-5 text-white" />
          </button>
          <button className="editor-button flex justify-center items-center p-1 w-[28px] h-[28px] rounded-full hover:bg-white/10">
            <Maximize2 className="w-5 h-5 text-white" />
          </button>
        </div>
        <div className="inner-ace w-full h-[600px] rounded-[8px] overflow-hidden">
          <AceEditor
            mode="python"
            theme="twilight"
            name="python-editor"
            // value={code}
            // onChange={onCodeChange}
            width="100%"
            height="100%"
            setOptions={{
              showLineNumbers: true,
              tabSize: 4,
              useWorker: false,
            }}
          />
        </div>
      </div>

      <div className="bg-gray-50 rounded-2xl p-4 !my-8 border-b border-gray-200 mb-8">
        <h2 className="text-sm font-semibold mb-4">Code Instructions:</h2>
        <ul className="list-disc list-inside text-sm text-gray-500 space-y-2">
          <li>Use params to access input parameters</li>
          <li>Store your return value in result variable</li>
          <li>Available libraries: json, requests, datetime, math, re</li>
          <li>Code runs in a sandboxed environment with limited resources</li>
        </ul>
      </div>

      <div className="flex py-2 px-3 border-b border-gray-200 pb-8">
        <Button
          variant="outline"
          //   onClick={handleGenerateTemplate}
          disabled={
            dynamicParams.length === 0 || dynamicParams.every((p) => !p.name)
          }
        >
          <CodeXml className="w-4 h-4 mr-2" /> Generate Template from Schema
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="font-semibold text-lg text-[#18181B]">
          Test Your Python Code
        </h3>
        <label className="text-sm text-gray-500 mb-2">
          Test Parameters (JSON)
        </label>
        <div className="relative p-6 h-[303px] bg-[#1C1C1C] rounded-[16px] overflow-hidden">
          <div className="absolute top-4 right-4 flex gap-2 z-10">
            <button
              onClick={() => {
                navigator.clipboard.writeText(testParameters);
                toast.success("Params copied.");
              }}
            >
              <ClipboardList className="w-5 h-5 text-white" />
            </button>
            <button>
              <Maximize2 className="w-5 h-5 text-white" />
            </button>
          </div>
          <div className="inner-ace w-full h-full rounded-[8px] overflow-hidden">
            <AceEditor
              mode="json"
              theme="twilight"
              name="params-editor"
              //   value={testParameters}
              //   onChange={onTestParametersChange}
              width="100%"
              height="240px"
              setOptions={{
                tabSize: 2,
                showLineNumbers: true,
                useWorker: false,
              }}
            />
          </div>
        </div>
        <div className="flex py-8">
          <Button
            variant="outline"
            // onClick={handleTestCode}
            disabled={testingCode}
          >
            <CirclePlay className="w-4 h-4 mr-2" />
            {testingCode ? "Testing..." : "Test Code"}
          </Button>
        </div>
      </div>
      <div className="relative p-6 h-[303px] bg-[#F7F9FB] rounded-[16px] overflow-hidden">
        <div className="absolute top-4 right-4 flex gap-2 z-10">
          <button
            onClick={() => {
              navigator.clipboard.writeText(testParameters);
              toast.success("Params copied.");
            }}
          >
            <ClipboardList className="w-5 h-5 text-black" />
          </button>
          <button>
            <Maximize2 className="w-5 h-5 text-black" />
          </button>
        </div>

        <div className="inner-aces w-full h-full bg-[#F7F9FB] rounded-[8px] overflow-hidden">
          <AceEditor
            mode="json"
            theme=""
            name="params-editor"
            //   value={testParameters}
            //   onChange={onTestParametersChange}
            width="100%"
            height="240px"
            setOptions={{
              tabSize: 2,
              showLineNumbers: true,
              useWorker: false,
            }}
          />
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</p>
      )}
      {success && (
        <p className="text-sm text-green-600 bg-green-50 p-2 rounded">
          {success}
        </p>
      )}
      {testResult && (
        <pre className="bg-gray-100 p-4 rounded max-h-96 overflow-auto font-mono text-sm">
          {testResult}
        </pre>
      )}
    </div>
  </div>
);
