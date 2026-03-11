export interface Translation {
  id?: string;
  key: string;
  default?: string | null;
  translations: Record<string, string>;
}

export interface Language {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}
