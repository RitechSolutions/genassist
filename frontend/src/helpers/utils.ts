import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
} 

export function getTimeFromDatetime(datetimeString: string): string {
  const date = new Date(datetimeString);
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const seconds = date.getSeconds();

  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

export function tryParse(value: any) {
  try {
    const first = JSON.parse(value);
    if (typeof first === "string") {
      try {
        return JSON.parse(first);
      } catch {
        return first;
      }
    }
    return first;
  } catch {
    return value;
  }
}

export function maskInput(inputVal: string, maxLength: number = 36): string {
  let maskSize = inputVal.length;  // default mask size
  if (inputVal.length > maxLength) {
    maskSize = maxLength;
  }
  return "*".repeat(maskSize);
}
