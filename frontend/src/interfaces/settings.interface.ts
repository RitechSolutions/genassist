import { ElementType } from 'react';

export type FieldType = "text" | "email" | "toggle" | "number" | "select" | "tags";

export interface SettingFieldType {
  label: string;
  type: FieldType;
  placeholder?: string;
  options?: string[];
  valueKey?: string;
  value?: string | number | boolean | string[];
  readOnly?: boolean;
  className?: string;
}

export interface SettingSectionType {
  title: string;
  icon: ElementType;
  description: string;
  fields: SettingFieldType[];
}