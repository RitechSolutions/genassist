export const EVALUATION_BUNDLE_KIND = "genassist.evaluation-bundle";

export interface BundleNodeRef {
  label?: string | null;
  kind: string;
  node_type?: string | null;
}

export interface BundleProviderRef {
  name?: string | null;
  provider?: string | null;
  model?: string | null;
}

export interface BundleCase {
  local_id: number;
  input_data: Record<string, unknown>;
  expected_output?: Record<string, unknown> | null;
  tags?: string[] | null;
  weight?: number | null;
  source_conversation_id?: string | null;
  turn_index?: number | null;
}

export interface EvaluationBundle {
  kind: string;
  schema_version: number;
  source: {
    workflow_id?: string | null;
    workflow_name?: string | null;
    workflow_version?: string | null;
  };
  evaluation: {
    name: string;
    description?: string | null;
    techniques: string[];
    technique_configs?: Record<string, unknown> | null;
    input_metadata?: Record<string, unknown> | null;
  };
  dataset: {
    name: string;
    description?: string | null;
    default_input_metadata?: Record<string, unknown> | null;
    cases: BundleCase[];
  };
  references: {
    nodes: Record<string, BundleNodeRef>;
    llm_providers: Record<string, BundleProviderRef>;
    cases: Record<string, number>;
  };
  notes: string[];
}

export interface BundleRefCandidate {
  id: string;
  label: string;
}

export interface BundleNodeResolution {
  ref: string;
  kind: string;
  label?: string | null;
  status: "resolved" | "ambiguous" | "missing";
  resolved_id?: string | null;
  resolved_label?: string | null;
  candidates: BundleRefCandidate[];
  note?: string | null;
  original_type?: string | null;
}

export interface BundleProviderResolution {
  ref: string;
  name?: string | null;
  model?: string | null;
  status: "resolved" | "missing";
  resolved_id?: string | null;
  resolved_name?: string | null;
}

export interface BundleExistingDataset {
  id: string;
  name: string;
  case_count: number;
}

export interface EvaluationImportPreview {
  evaluation_name: string;
  dataset_name: string;
  case_count: number;
  existing_dataset?: BundleExistingDataset | null;
  workflow_name_matches: boolean;
  node_refs: BundleNodeResolution[];
  provider_refs: BundleProviderResolution[];
  warnings: string[];
  can_import: boolean;
  dropping_all_would_empty?: boolean;
}

export interface EvaluationImportResult {
  evaluation_id: string;
  suite_id: string;
  case_count: number;
  reused_dataset: boolean;
  dropped_rules: string[];
  warnings: string[];
}

export const EVALUATION_BUNDLE_SET_KIND = "genassist.evaluation-bundle-set";

export interface BundleSetDataset {
  local_id: number;
  name: string;
  description?: string | null;
  default_input_metadata?: Record<string, unknown> | null;
  cases: BundleCase[];
}

export interface BundleSetItem {
  evaluation: EvaluationBundle["evaluation"];
  dataset_local_id: number;
  references: EvaluationBundle["references"];
  notes?: string[];
}

export interface EvaluationBundleSet {
  kind: string;
  schema_version: number;
  source: EvaluationBundle["source"];
  datasets: BundleSetDataset[];
  evaluations: BundleSetItem[];
  notes: string[];
}

export interface EvaluationSetItemPreview {
  name: string;
  dataset_name: string;
  case_count: number;
  already_exists: boolean;
  dropping_all_would_empty: boolean;
  node_ref_keys?: string[];
}

export interface BundleSetDatasetPreview {
  local_id: number;
  name: string;
  case_count: number;
  existing_dataset?: BundleExistingDataset | null;
}

export interface EvaluationSetImportPreview {
  workflow_name_matches: boolean;
  evaluations: EvaluationSetItemPreview[];
  datasets: BundleSetDatasetPreview[];
  node_refs: BundleNodeResolution[];
  provider_refs: BundleProviderResolution[];
  warnings: string[];
  can_import: boolean;
}

export type SetItemStatus = "imported" | "skipped" | "failed";

export interface EvaluationSetItemResult {
  name: string;
  status: SetItemStatus | string;
  evaluation_id?: string | null;
  suite_id?: string | null;
  case_count: number;
  reused_dataset: boolean;
  dropped_rules: string[];
  warnings: string[];
  detail?: string | null;
}

export interface EvaluationSetImportResult {
  results: EvaluationSetItemResult[];
  imported: number;
  skipped: number;
  failed: number;
}
