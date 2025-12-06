import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";
import { ChevronDown, ChevronRight, Settings } from "lucide-react";
import { getRagFromSchema } from "@/services/api";
import { finalizeKnowledgeItem } from "@/services/api";
import { toast } from "react-hot-toast";
import { DynamicRagField } from "./DynamicRagField";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { RagConfigValues } from "../types/ragSchema";


interface DynamicRagConfigSectionProps {
  ragConfig?: RagConfigValues;
  onChange: (updatedRagConfig: RagConfigValues) => void;
  showOnlyRequired?: boolean;
  knowledgeId?: string;
  initialLegraFinalize?: boolean;
}

const DynamicRagConfigSection: React.FC<DynamicRagConfigSectionProps> = ({
  ragConfig = {},
  onChange,
  showOnlyRequired = false,
  knowledgeId,
  initialLegraFinalize = false,
}) => {
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  const [isInitialized, setIsInitialized] = useState(false);
  const [showOptionalFields, setShowOptionalFields] = useState(
    !showOnlyRequired
  );
  const [legraFinalize, setLegraFinalize] = useState<boolean>(Boolean(initialLegraFinalize));
  const [isFinalizing, setIsFinalizing] = useState<boolean>(false);

  const {
    data: schema,
    isLoading,
    error,
  } = useQuery<DynamicFormSchema>({
    queryKey: ["ragConfigSchema"],
    queryFn: getRagFromSchema,
  });

  // Initialize default values based on schema when schema loads
  useEffect(() => {
    if (schema && !isInitialized) {
      const initialConfig: RagConfigValues = { ...ragConfig };
      let hasChanges = false;

      Object.entries(schema).forEach(([ragType, typeSchema]) => {
        if (!initialConfig[ragType]) {
          initialConfig[ragType] = {
            enabled: false,
          };
          hasChanges = true;
        }

        typeSchema.sections.forEach((section) => {
          // Initialize regular fields
          section.fields.forEach((field) => {
            if (field.default !== undefined && initialConfig[ragType][field.name] === undefined) {
              initialConfig[ragType][field.name] = field.default;
              hasChanges = true;
            }
          });

          // Initialize conditional fields defaults based on current values
          if (section.conditional_fields) {
            // Find the controlling field (field whose options match conditional_fields keys)
            const controllingField = section.fields.find(field => {
              if (!field.options || !section.conditional_fields) return false;
              return field.options.some(option => 
                Object.keys(section.conditional_fields!).includes(option.value)
              );
            });
            
            if (controllingField) {
              const controlValue = initialConfig[ragType][controllingField.name] || controllingField.default;
              const conditionalFields = section.conditional_fields[controlValue as string];
              
              if (conditionalFields) {
                conditionalFields.forEach((field) => {
                  if (field.default !== undefined && initialConfig[ragType][field.name] === undefined) {
                    initialConfig[ragType][field.name] = field.default;
                    hasChanges = true;
                  }
                });
              }
            }
          }
        });
      });

      if (hasChanges) {
        onChange(initialConfig);
      }
      setIsInitialized(true);
    }
  }, [schema, ragConfig, onChange, isInitialized]);

  const toggleSection = (sectionKey: string) => {
    setOpenSections((prev) => ({
      ...prev,
      [sectionKey]: !prev[sectionKey],
    }));
  };

  const handleRagTypeToggle = (ragType: string, enabled: boolean) => {
    const updatedConfig = {
      ...ragConfig,
      [ragType]: {
        ...ragConfig[ragType],
        enabled,
      },
    };
    onChange(updatedConfig);
  };

  const handleFieldChange = (
    ragType: string,
    fieldName: string,
    value: unknown
  ) => {
    const updatedConfig = {
      ...ragConfig,
      [ragType]: {
        ...ragConfig[ragType],
        [fieldName]: value,
      },
    };

    // If this field change affects conditional fields, initialize defaults for newly visible fields
    if (schema) {
      const typeSchema = schema[ragType];
      // Find which section this field belongs to for conditional field logic
      const section = typeSchema?.sections.find(s => 
        s.fields.some(f => f.name === fieldName) ||
        (s.conditional_fields && Object.values(s.conditional_fields).some(fields => 
          fields.some(f => f.name === fieldName)
        ))
      );
      
      if (section?.conditional_fields && section.conditional_fields[value as string]) {
        const conditionalFields = section.conditional_fields[value as string];
        
        conditionalFields.forEach((field) => {
          if (field.default !== undefined && updatedConfig[ragType][field.name] === undefined) {
            updatedConfig[ragType][field.name] = field.default;
          }
        });
      }
    }

    onChange(updatedConfig);
  };

  const getFieldValue = (
    ragType: string,
    fieldName: string
  ): unknown => {
    return ragConfig[ragType]?.[fieldName];
  };

  const handleLegraFinalizeToggle = async (checked: boolean) => {
    if (!knowledgeId) return;
    if (legraFinalize) return;
    if (!checked) return;
    try {
      setIsFinalizing(true);
      await finalizeKnowledgeItem(knowledgeId);
      setLegraFinalize(true);
      toast.success("Finalized successfully.");
    } catch (err) {
      toast.error("Failed to finalize.");
    } finally {
      setIsFinalizing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="grid grid-cols-3 gap-6">
          <div>
            <h3 className="text-lg font-semibold">RAG Configuration</h3>
            <p className="text-sm text-gray-500 mt-1">
              Loading configuration options...
            </p>
          </div>
          <div className="col-span-2">
            <div className="animate-pulse space-y-4">
              <div className="h-20 bg-gray-200 rounded"></div>
              <div className="h-20 bg-gray-200 rounded"></div>
              <div className="h-20 bg-gray-200 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="grid grid-cols-3 gap-6">
          <div>
            <h3 className="text-lg font-semibold">RAG Configuration</h3>
            <p className="text-sm text-gray-500 mt-1">
              Configure Retrieval Augmented Generation settings
            </p>
          </div>
          <div className="col-span-2">
            <div className="text-red-500 text-sm">
              Failed to load RAG configuration schema. Please try again.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!schema) {
    return null;
  }

  return (
    <div className="p-6">
      <div className="grid grid-cols-3 gap-6">
        <div>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">RAG Configuration</h3>
              <p className="text-sm text-gray-500 mt-1">
                Configure Retrieval Augmented Generation settings
              </p>
            </div>
            {/* <div className="flex items-center space-x-2 bg-gray-50 p-2 rounded-lg">
              <Settings className="h-4 w-4 text-gray-500" />
              <Label htmlFor="show-optional" className="text-sm font-medium">
                Show optional fields
              </Label>
              <Switch
                id="show-optional"
                checked={showOptionalFields}
                onCheckedChange={setShowOptionalFields}
              />
            </div> */}
          </div>
        </div>

        <div className="col-span-2 space-y-4">
          {Object.entries(schema).map(([ragType, typeSchema]) => {
            const isEnabled = Boolean(ragConfig[ragType]?.enabled);

            return (
              <Card key={ragType} className="w-full">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-base">
                        {typeSchema.name}
                      </CardTitle>
                      <p className="text-sm text-gray-500 mt-1">
                        {typeSchema.description}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      <Label htmlFor={`${ragType}-enabled`} className="text-sm">
                        Enable
                      </Label>
                      <Switch
                        id={`${ragType}-enabled`}
                        checked={isEnabled}
                        onCheckedChange={(checked) =>
                          handleRagTypeToggle(ragType, checked)
                        }
                      />
                    </div>
                  </div>
                </CardHeader>

                {isEnabled && (
                  <CardContent className="pt-0">
                    <div className="space-y-4">
                      {typeSchema.sections
                        .filter(
                          (section) =>
                            showOptionalFields ||
                            section.fields.some((field) => field.required)
                        )
                        .map((section) => {
                          const sectionKey = `${ragType}-${section.name}`;
                          const isSectionOpen =
                            openSections[sectionKey] ?? false;

                          return (
                            <Collapsible
                              key={section.name}
                              open={isSectionOpen}
                              onOpenChange={() => toggleSection(sectionKey)}
                            >
                              <CollapsibleTrigger className="flex items-center justify-between w-full p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                                <h4 className="text-sm font-medium">
                                  {section.label}
                                </h4>
                                {isSectionOpen ? (
                                  <ChevronDown className="h-4 w-4" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                              </CollapsibleTrigger>
                              <CollapsibleContent className="mt-3">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4">
                                  {/* Regular fields */}
                                  {(() => {
                                    const nodes: React.ReactNode[] = [];
                                    section.fields
                                      .filter((field) => showOptionalFields || field.required)
                                      .forEach((field) => {
                                        nodes.push(
                                          <DynamicRagField
                                            key={field.name}
                                            field={field}
                                            value={getFieldValue(ragType, field.name)}
                                            onChange={(fieldName, value) =>
                                              handleFieldChange(ragType, fieldName, value)
                                            }
                                          />
                                        );

                                        const isLegra = ragType.toLowerCase() === "legra" ||
                                          (typeSchema?.name || "").toLowerCase().includes("legra");
                                        const sectionLabelLc = (section.label || "").trim().toLowerCase();
                                        const sectionNameLc = (section.name || "").trim().toLowerCase();
                                        const isLegraEmbeddingSection =
                                          sectionLabelLc === "embedding configuration" ||
                                          sectionLabelLc.includes("embedding") ||
                                          sectionNameLc.includes("embedding");
                                        const isEmbeddingModelField =
                                          field.name === "embedding_model" ||
                                          (field.label || "").toLowerCase() === "embedding model";
                                        if (isLegra && isLegraEmbeddingSection && isEmbeddingModelField) {
                                          nodes.push(
                                            <div key="legra-embedding-finalize" className="space-y-2">
                                              <Label htmlFor="legra-embedding-finalize" className="text-sm font-medium">
                                                Finalize
                                              </Label>
                                              <div className="mt-2">
                                                <div className="flex items-center gap-2">
                                                  <Switch
                                                    id="legra-embedding-finalize"
                                                    checked={legraFinalize}
                                                    disabled={isFinalizing || legraFinalize || !knowledgeId}
                                                    onCheckedChange={handleLegraFinalizeToggle}
                                                  />
                                                  <span className="text-sm text-gray-500">
                                                    {legraFinalize ? "Finalized" : (!knowledgeId ? "Save first to enable" : "Finalize to lock and build graph")}
                                                  </span>
                                                </div>
                                                <p className="text-xs text-gray-500 mt-2">This action cannot be undone.</p>
                                              </div>
                                            </div>
                                          );
                                        }
                                      });
                                    return nodes;
                                  })()}
                                  
                                  {/* Conditional fields */}
                                  {section.conditional_fields && (() => {
                                    // Find the controlling field value
                                    const controllingField = section.fields.find(field => {
                                      if (!field.options || !section.conditional_fields) return false;
                                      return field.options.some(option => 
                                        Object.keys(section.conditional_fields!).includes(option.value)
                                      );
                                    });
                                    
                                    if (!controllingField) return null;
                                    
                                    const controlValue = getFieldValue(
                                      ragType,
                                      controllingField.name
                                    ) as string;
                                    
                                    const conditionalFields = section.conditional_fields[controlValue];
                                    
                                    if (!conditionalFields) return null;
                                    
                                    return conditionalFields
                                      .filter(
                                        (field) =>
                                          showOptionalFields || field.required
                                      )
                                      .map((field) => (
                                        <DynamicRagField
                                          key={`conditional-${field.name}`}
                                          field={field}
                                          value={getFieldValue(
                                            ragType,
                                            field.name
                                          )}
                                          onChange={(fieldName, value) =>
                                            handleFieldChange(
                                              ragType,
                                              fieldName,
                                              value
                                            )
                                          }
                                        />
                                      ));
                                  })()}
                                </div>
                              </CollapsibleContent>
                            </Collapsible>
                          );
                        })}
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default DynamicRagConfigSection;
