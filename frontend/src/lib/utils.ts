import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combines multiple class names or conditional class values using clsx and twMerge
 * This allows for cleaner className prop definitions with proper Tailwind merging
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
} 