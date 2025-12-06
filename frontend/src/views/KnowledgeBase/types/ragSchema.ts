export interface RagConfigValues {
  [ragType: string]: {
    enabled: boolean;
    [fieldName: string]: unknown;
  };
}
