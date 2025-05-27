import { ElementType } from 'react';

export type FieldType = "text" | "email" | "toggle" | "number" | "select";

export interface SettingFieldType {
  label: string;
  type: FieldType;
  placeholder?: string;
  options?: string[];
}

export interface SettingSectionType {
  title: string;
  icon: ElementType;
  description: string;
  fields: SettingFieldType[];
} 