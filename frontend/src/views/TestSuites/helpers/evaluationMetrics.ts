export const accuracyColorClass = (accuracy: number): string => {
  if (accuracy >= 0.9) return "text-green-600";
  if (accuracy >= 0.7) return "text-amber-600";
  return "text-red-600";
};
