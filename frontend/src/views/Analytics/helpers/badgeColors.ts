export const getChangeBadgeColor = (
  changeType: "increase" | "decrease" | "neutral",
) => {
  switch (changeType) {
    case "increase":
      return "bg-green-200";
    case "decrease":
      return "bg-red-200";
    case "neutral":
      return "bg-zinc-200";
  }
};

export const getChangeTextColor = (
  changeType: "increase" | "decrease" | "neutral",
) => {
  switch (changeType) {
    case "increase":
      return "text-green-600";
    case "decrease":
      return "text-red-600";
    case "neutral":
      return "text-zinc-600";
  }
};

export const getChangeIconColor = (
  changeType: "increase" | "decrease" | "neutral",
) => {
  switch (changeType) {
    case "increase":
      return "text-green-700";
    case "decrease":
      return "text-red-700";
    case "neutral":
      return "text-zinc-600";
  }
};
