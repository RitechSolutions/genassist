import { Permission } from "@/interfaces/permission.interface";

/**
 * Turns the flat `verb:resource` permission strings into the two-level
 * structure the role dialog renders: areas -> resource rows -> verb entries.
 *
 * Grouping by raw resource alone gives 40+ groups, half of them single
 * permissions, so resources are folded into a curated set of areas. Anything
 * not mapped falls into "Other", which keeps newly added permissions visible
 * instead of silently dropping them from the UI.
 */

export interface PermissionEntry {
  id: string;
  name: string;
  verb: string;
  verbLabel: string;
  description?: string | null;
  isAdminOnly: boolean;
}

export interface ResourceRow {
  key: string;
  label: string;
  entries: PermissionEntry[];
}

export interface PermissionArea {
  key: string;
  label: string;
  /** True when every permission in the area is admin-reserved. */
  isAdminOnly: boolean;
  rows: ResourceRow[];
  permissionIds: string[];
}

// Permission names that don't follow "verb:resource".
const IRREGULAR_NAMES: Record<string, { verb: string; resource: string }> = {
  takeover_in_progress_conversation: {
    verb: "takeover",
    resource: "in_progress_conversation",
  },
};

// Resource spellings that differ from the rest of their family.
const RESOURCE_ALIASES: Record<string, string> = {
  "openai-file": "openai_file",
};

const VERB_LABELS: Record<string, string> = {
  read: "View",
  create: "Create",
  update: "Edit",
  delete: "Delete",
  write: "Write",
  execute: "Run",
  run: "Run",
  test: "Test",
  deploy: "Deploy",
  undeploy: "Undeploy",
  cancel: "Cancel",
  decrypt: "Reveal",
  switch: "Switch",
  install: "Install",
  publish: "Publish",
  approve: "Approve",
  takeover: "Take over",
};

// Familiar CRUD order first; anything else keeps its alphabetical position after.
const VERB_ORDER = ["read", "create", "update", "delete", "write"];

const RESOURCE_LABELS: Record<string, string> = {
  agent: "Agent switching",
  analyze_recording: "Recording analysis",
  api_key: "API keys",
  app_settings: "Application settings",
  ask_question: "Transcript questions",
  audit_log: "Audit log",
  bedrock_fine_tunable_models: "Bedrock tunable models",
  bedrock_job: "Bedrock jobs",
  bedrock_model: "Bedrock models",
  bedrock_training_data: "Bedrock training data",
  conversation: "Conversations",
  "conversation:gdpr": "GDPR deletion",
  customer: "Customers",
  dashboard: "Dashboard",
  data_source: "Data sources",
  evaluation: "Evaluations",
  feature_flag: "Feature flags",
  file: "Files",
  files: "Recording files",
  in_progress_conversation: "Live conversations",
  knowledge_base: "Knowledge base",
  llm_analyst: "LLM analysts",
  llm_provider: "LLM providers",
  local_fine_tuning: "Local fine-tuning",
  metrics: "Recording metrics",
  ml_model: "ML models",
  openai_file: "OpenAI files",
  openai_fine_tunable_models: "OpenAI tunable models",
  openai_fine_tuned_model: "OpenAI tuned models",
  openai_job: "OpenAI jobs",
  operator: "Operators",
  permission: "Permissions",
  recording: "Recordings",
  role: "Roles",
  role_permission: "Role permissions",
  template: "Templates",
  tenant: "Tenants",
  upload_transcript: "Transcript upload",
  user: "Users",
  user_group: "User groups",
  user_type: "User types",
  workflow: "Workflows",
};

const AREA_DEFINITIONS: Array<{ key: string; label: string; resources: string[] }> = [
  {
    key: "conversations",
    label: "Conversations",
    resources: ["conversation", "in_progress_conversation", "conversation:gdpr"],
  },
  {
    key: "recordings",
    label: "Recordings & transcripts",
    resources: [
      "recording",
      "files",
      "metrics",
      "analyze_recording",
      "upload_transcript",
      "ask_question",
    ],
  },
  {
    key: "automation",
    label: "Workflows & agents",
    resources: ["workflow", "agent", "evaluation"],
  },
  {
    key: "knowledge",
    label: "Knowledge & content",
    resources: ["data_source", "knowledge_base", "file", "template"],
  },
  {
    key: "models",
    label: "Models & credentials",
    resources: ["llm_provider", "llm_analyst", "ml_model", "api_key"],
  },
  {
    key: "fine_tuning",
    label: "Fine-tuning",
    resources: [
      "openai_file",
      "openai_job",
      "openai_fine_tunable_models",
      "openai_fine_tuned_model",
      "bedrock_job",
      "bedrock_model",
      "bedrock_training_data",
      "bedrock_fine_tunable_models",
      "local_fine_tuning",
    ],
  },
  {
    key: "access",
    label: "Access control",
    resources: [
      "user",
      "user_group",
      "user_type",
      "role",
      "role_permission",
      "permission",
      "operator",
      "tenant",
    ],
  },
  { key: "customers", label: "Customers", resources: ["customer"] },
  { key: "insights", label: "Insights", resources: ["dashboard", "audit_log"] },
  {
    key: "configuration",
    label: "Configuration",
    resources: ["app_settings", "feature_flag"],
  },
];

const OTHER_AREA_KEY = "other";

const AREA_BY_RESOURCE = new Map<string, string>();
AREA_DEFINITIONS.forEach((area) =>
  area.resources.forEach((resource) => AREA_BY_RESOURCE.set(resource, area.key))
);

/** Splits a permission name into its verb and resource. */
export function parsePermissionName(name: string): { verb: string; resource: string } {
  const irregular = IRREGULAR_NAMES[name];
  if (irregular) return irregular;

  const separator = name.indexOf(":");
  if (separator === -1) return { verb: "access", resource: name };

  const verb = name.slice(0, separator);
  const rawResource = name.slice(separator + 1);
  return { verb, resource: RESOURCE_ALIASES[rawResource] ?? rawResource };
}

function humanize(value: string): string {
  const spaced = value.replace(/[_:-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function resourceLabel(resource: string): string {
  return RESOURCE_LABELS[resource] ?? humanize(resource);
}

export function verbLabel(verb: string): string {
  return VERB_LABELS[verb] ?? humanize(verb);
}

function compareVerbs(a: string, b: string): number {
  const aIndex = VERB_ORDER.indexOf(a);
  const bIndex = VERB_ORDER.indexOf(b);
  if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
  if (aIndex !== -1) return -1;
  if (bIndex !== -1) return 1;
  return a.localeCompare(b);
}

/** Groups permissions into areas, preserving the curated area and verb order. */
export function buildPermissionAreas(permissions: Permission[]): PermissionArea[] {
  const rowsByResource = new Map<string, ResourceRow>();

  permissions.forEach((permission) => {
    const { verb, resource } = parsePermissionName(permission.name);

    let row = rowsByResource.get(resource);
    if (!row) {
      row = { key: resource, label: resourceLabel(resource), entries: [] };
      rowsByResource.set(resource, row);
    }

    row.entries.push({
      id: permission.id,
      name: permission.name,
      verb,
      verbLabel: verbLabel(verb),
      description: permission.description,
      isAdminOnly: permission.is_admin_only === true,
    });
  });

  rowsByResource.forEach((row) => row.entries.sort((a, b) => compareVerbs(a.verb, b.verb)));

  const rowsByArea = new Map<string, ResourceRow[]>();
  rowsByResource.forEach((row, resource) => {
    const areaKey = AREA_BY_RESOURCE.get(resource) ?? OTHER_AREA_KEY;
    const existing = rowsByArea.get(areaKey);
    if (existing) existing.push(row);
    else rowsByArea.set(areaKey, [row]);
  });

  const ordered: PermissionArea[] = [];

  const pushArea = (key: string, label: string, rows: ResourceRow[], order?: string[]) => {
    if (rows.length === 0) return;

    const sorted = order
      ? [...rows].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
      : [...rows].sort((a, b) => a.label.localeCompare(b.label));

    const entries = sorted.flatMap((row) => row.entries);
    ordered.push({
      key,
      label,
      isAdminOnly: entries.every((entry) => entry.isAdminOnly),
      rows: sorted,
      permissionIds: entries.map((entry) => entry.id),
    });
  };

  AREA_DEFINITIONS.forEach((area) =>
    pushArea(area.key, area.label, rowsByArea.get(area.key) ?? [], area.resources)
  );
  pushArea(OTHER_AREA_KEY, "Other", rowsByArea.get(OTHER_AREA_KEY) ?? []);

  return ordered;
}

/**
 * Which areas start collapsed: every area the role draws nothing from. A new
 * role selects nothing, so all of them collapse and the whole permission model
 * is visible at a glance; an existing role opens with just the areas it uses.
 */
export function collapsedAreasFor(
  areas: PermissionArea[],
  selectedIds: Iterable<string>
): Set<string> {
  const selected = new Set(selectedIds);

  return new Set(
    areas
      .filter((area) => !area.permissionIds.some((id) => selected.has(id)))
      .map((area) => area.key)
  );
}

/**
 * A plain-language read of what the selection grants, so the admin can sanity
 * check a role without decoding permission strings.
 */
export function summarizeCapabilities(
  areas: PermissionArea[],
  selectedIds: Set<string>
): string[] {
  const phrases: string[] = [];

  areas.forEach((area) => {
    const selected = area.rows
      .flatMap((row) => row.entries)
      .filter((entry) => selectedIds.has(entry.id));
    if (selected.length === 0) return;

    const canOnlyView = selected.every((entry) => entry.verb === "read");
    const label = area.label.toLowerCase();
    phrases.push(canOnlyView ? `view ${label}` : `manage ${label}`);
  });

  return phrases;
}
