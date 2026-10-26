import type { CategoryQuery } from "@/services/testEvaluations";

export const CATEGORY_MAX_LENGTH = 50;

/** A category as it is saved: spaces trimmed and collapsed. */
export const tidyCategory = (text: string): string => text.trim().replace(/\s+/g, " ");

// Letter by letter like the database's lower() (which lowers "İ" to "i"), whatever the browser's language.
const caseless = (text: string): string =>
  Array.from(text, (letter) => (letter === "İ" ? "i" : letter.toLowerCase())).join("");

/** What the picker lists for the typed text, matched on the tidied text so extra spaces hide nothing. */
export const pickerChoices = (text: string, value: string, categories: string[]) => {
  const typed = tidyCategory(text);
  const wanted = caseless(typed);
  // One added in the form but not saved yet is listed too.
  const names = value && !categories.includes(value) ? [value, ...categories] : categories;
  return {
    typed,
    // Typed in another case, a category in use is picked, not added again.
    isNew: Boolean(typed) && !names.some((name) => caseless(name) === wanted),
    shown: typed ? names.filter((name) => caseless(name).includes(wanted)) : names,
  };
};

// A category filter's choices: every category, none set, or one of them.
export const ALL_CATEGORIES = "all";
export const NO_CATEGORY = "none";
const PREFIX = "category:";

/** The filter's value for one category, kept apart from the two choices above. */
export const categoryOption = (name: string): string => `${PREFIX}${name}`;

/** What the API is asked for: a category, none set, or nothing. */
export const categoryQuery = (value: string): CategoryQuery => {
  if (value === NO_CATEGORY) return { uncategorized: true };
  if (value.startsWith(PREFIX)) return { category: value.slice(PREFIX.length) };
  return {};
};

/** Which of a workflow's evaluations Run all starts under the filter, in words. */
export const runAllScope = (value: string, workflowName: string): string => {
  const { category, uncategorized } = categoryQuery(value);
  if (uncategorized) return `the evaluations of ${workflowName} that have no category`;
  if (category) return `the evaluations of ${workflowName} in the category “${category}”`;
  return `every evaluation of ${workflowName}`;
};

/** Whether an item with this category passes the filter, for lists filtered in the page. */
export const matchesCategory = (category: string | null | undefined, value: string): boolean => {
  if (value === NO_CATEGORY) return !category;
  if (!value.startsWith(PREFIX)) return true;
  return caseless(category ?? "") === caseless(value.slice(PREFIX.length));
};
