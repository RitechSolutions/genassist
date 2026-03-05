/**
 * RagVectorConfigSection
 *
 * Renders only the "vector" type from the shared RAG schema, without the
 * enable/disable toggle or multi-type card layout. Intended for embedding
 * inline inside the agent memory config and ThreadRAGNode dialog.
 *
 * The config shape matches the flat field names produced by agent_rag_form_schemas.py
 * (e.g. "embedding_type", "vector_db_type", "chunk_strategy") — the same values
 * that _create_default_config() in rag.py reads from config_overrides.
 */
import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { getRagFromSchema } from "@/services/api";
import { DynamicRagField } from "./DynamicRagField";
import { DynamicFormSchema } from "@/interfaces/dynamicFormSchemas.interface";

interface RagVectorConfigSectionProps {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}

const RagVectorConfigSection: React.FC<RagVectorConfigSectionProps> = ({
  config,
  onChange,
}) => {
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  const [isInitialized, setIsInitialized] = useState(false);

  const { data: schema, isLoading, error } = useQuery<DynamicFormSchema>({
    queryKey: ["ragConfigSchema"],
    queryFn: getRagFromSchema,
  });

  // Seed defaults from schema on first load
  useEffect(() => {
    if (!schema || isInitialized) return;
    const vectorSchema = schema["vector"];
    if (!vectorSchema) return;

    const initial: Record<string, unknown> = { ...config };
    let changed = false;

    vectorSchema.sections.filter((s) => s.name !== "chunking").forEach((section) => {
      section.fields.filter((f) => f.required).forEach((field) => {
        if (field.default !== undefined && initial[field.name] === undefined) {
          initial[field.name] = field.default;
          changed = true;
        }
      });

      if (section.conditional_fields) {
        const controllingField = section.fields.find(
          (f) =>
            f.options &&
            f.options.some((o) =>
              Object.keys(section.conditional_fields!).includes(o.value)
            )
        );
        if (controllingField) {
          const controlValue =
            (initial[controllingField.name] as string) ??
            controllingField.default;
          const conditionals = section.conditional_fields[controlValue as string];
          conditionals?.filter((f) => f.required).forEach((field) => {
            if (field.default !== undefined && initial[field.name] === undefined) {
              initial[field.name] = field.default;
              changed = true;
            }
          });
        }
      }
    });

    if (changed) onChange(initial);
    setIsInitialized(true);
  }, [schema, config, onChange, isInitialized]);

  const handleFieldChange = (fieldName: string, value: unknown) => {
    const updated = { ...config, [fieldName]: value };

    // Seed defaults for newly revealed conditional fields
    if (schema) {
      const vectorSchema = schema["vector"];
      vectorSchema?.sections.filter((s) => s.name !== "chunking").forEach((section) => {
        if (
          section.conditional_fields &&
          section.conditional_fields[value as string]
        ) {
          section.conditional_fields[value as string]
            .filter((f) => f.required)
            .forEach((field) => {
              if (field.default !== undefined && updated[field.name] === undefined) {
                updated[field.name] = field.default;
              }
            });
        }
      });
    }

    onChange(updated);
  };

  const toggleSection = (key: string) =>
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        <div className="h-8 bg-muted rounded" />
        <div className="h-8 bg-muted rounded" />
      </div>
    );
  }

  if (error || !schema?.["vector"]) return null;

  const vectorSchema = schema["vector"];

  return (
    <div className="space-y-2">
      {vectorSchema.sections.filter((s) => s.name !== "chunking").map((section) => {
        const isOpen = openSections[section.name] ?? false;

        // Determine the controlling field and its current value for this section
        const controllingField = section.conditional_fields
          ? section.fields.find(
              (f) =>
                f.options &&
                f.options.some((o) =>
                  Object.keys(section.conditional_fields!).includes(o.value)
                )
            )
          : undefined;

        const controlValue = controllingField
          ? ((config[controllingField.name] as string) ??
              controllingField.default)
          : undefined;

        const conditionalFields =
          controlValue && section.conditional_fields
            ? section.conditional_fields[controlValue as string] ?? []
            : [];

        return (
          <Collapsible
            key={section.name}
            open={isOpen}
            onOpenChange={() => toggleSection(section.name)}
          >
            <CollapsibleTrigger className="flex items-center justify-between w-full px-3 py-2 bg-muted/50 rounded-md hover:bg-muted transition-colors text-sm font-medium">
              {section.label}
              {isOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-3 space-y-3 px-1">
              {section.fields.filter((f) => f.required).map((field) => (
                <DynamicRagField
                  key={field.name}
                  field={field}
                  value={config[field.name]}
                  onChange={handleFieldChange}
                />
              ))}
              {conditionalFields.filter((f) => f.required).map((field) => (
                <DynamicRagField
                  key={`cond-${field.name}`}
                  field={field}
                  value={config[field.name]}
                  onChange={handleFieldChange}
                />
              ))}
            </CollapsibleContent>
          </Collapsible>
        );
      })}
    </div>
  );
};

export default RagVectorConfigSection;