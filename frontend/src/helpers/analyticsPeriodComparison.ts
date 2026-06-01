import {
  addYears,
  differenceInCalendarDays,
  endOfMonth,
  endOfWeek,
  endOfYear,
  startOfDay,
  startOfMonth,
  startOfWeek,
  startOfYear,
  subDays,
  subMonths,
  subWeeks,
  subYears,
} from "date-fns";
import type { DateRange } from "react-day-picker";
import {
  alignPeriodsByRelativeIndex,
  compareSeriesKey,
  enumerateDateRange,
  formatChartDayLabel,
} from "@/helpers/alignChartPeriods";

export type PeriodPreset =
  | "today"
  | "last7days"
  | "last30days"
  | "thisWeek"
  | "thisMonth"
  | "lastMonth"
  | "yearToDate"
  | "lastYear"
  | "custom";

export const PERIOD_PRESET_BY_LABEL: Record<string, PeriodPreset> = {
  Today: "today",
  "Last 7 days": "last7days",
  "Last 30 days": "last30days",
  "This week": "thisWeek",
  "This month": "thisMonth",
  "Last month": "lastMonth",
  "Year to date": "yearToDate",
  "Last year": "lastYear",
};

export type ComparisonPeriodResult = {
  selectedStartDate: Date;
  selectedEndDate: Date;
  comparisonStartDate: Date;
  comparisonEndDate: Date;
  selectedRange: DateRange;
  comparisonRange: DateRange;
};

function precedingPeriodSameLength(selectedStart: Date, selectedEnd: Date): {
  from: Date;
  to: Date;
} {
  const start = startOfDay(selectedStart);
  const end = startOfDay(selectedEnd);
  const dayCount = differenceInCalendarDays(end, start) + 1;
  const comparisonEnd = subDays(start, 1);
  const comparisonStart = subDays(comparisonEnd, dayCount - 1);
  return { from: comparisonStart, to: comparisonEnd };
}

/**
 * Derive the comparison period from the selected range and how it was chosen.
 * Selected dates from the picker are always the source of truth.
 */
export function getComparisonPeriod(
  selectedPeriod: DateRange,
  periodPreset: PeriodPreset,
): ComparisonPeriodResult | null {
  if (!selectedPeriod.from || !selectedPeriod.to) return null;

  const selectedStartDate = startOfDay(selectedPeriod.from);
  const selectedEndDate = startOfDay(selectedPeriod.to);
  const selectedRange: DateRange = { from: selectedStartDate, to: selectedEndDate };

  let comparisonStartDate: Date;
  let comparisonEndDate: Date;

  switch (periodPreset) {
    case "today":
    case "last7days":
    case "last30days":
    case "custom": {
      const preceding = precedingPeriodSameLength(selectedStartDate, selectedEndDate);
      comparisonStartDate = preceding.from;
      comparisonEndDate = preceding.to;
      break;
    }
    case "thisWeek": {
      const anchor = selectedEndDate;
      const prevWeek = subWeeks(anchor, 1);
      comparisonStartDate = startOfWeek(prevWeek, { weekStartsOn: 1 });
      comparisonEndDate = endOfWeek(prevWeek, { weekStartsOn: 1 });
      break;
    }
    case "thisMonth": {
      const prevMonth = subMonths(selectedEndDate, 1);
      comparisonStartDate = startOfMonth(prevMonth);
      comparisonEndDate = endOfMonth(prevMonth);
      break;
    }
    case "lastMonth": {
      const monthBefore = subMonths(selectedStartDate, 1);
      comparisonStartDate = startOfMonth(monthBefore);
      comparisonEndDate = endOfMonth(monthBefore);
      break;
    }
    case "yearToDate":
    case "lastYear": {
      comparisonStartDate = startOfDay(addYears(selectedStartDate, -1));
      comparisonEndDate = startOfDay(addYears(selectedEndDate, -1));
      break;
    }
    default: {
      const preceding = precedingPeriodSameLength(selectedStartDate, selectedEndDate);
      comparisonStartDate = preceding.from;
      comparisonEndDate = preceding.to;
    }
  }

  return {
    selectedStartDate,
    selectedEndDate,
    comparisonStartDate,
    comparisonEndDate,
    selectedRange,
    comparisonRange: { from: comparisonStartDate, to: comparisonEndDate },
  };
}

export type ComparisonChartRow = {
  label: string;
  name: string;
  selectedDate: string;
  comparisonDate: string | null;
  [metricKey: string]: string | number | null;
};

export function buildComparisonChartData<M extends string>(config: {
  selectedRange: DateRange;
  comparisonRange: DateRange | undefined;
  metrics: readonly M[];
  getValuesForDate: (date: string, period: "selected" | "comparison") => Record<M, number>;
}): ComparisonChartRow[] {
  const { selectedRange, comparisonRange, metrics, getValuesForDate } = config;

  if (!selectedRange.from || !selectedRange.to) return [];

  const hasComparison = Boolean(comparisonRange?.from && comparisonRange?.to);

  if (!hasComparison) {
    return enumerateDateRange(selectedRange).map((selectedDate) => {
      const values = getValuesForDate(selectedDate, "selected");
      const label = formatChartDayLabel(selectedDate);
      const row: ComparisonChartRow = {
        label,
        name: label,
        selectedDate,
        comparisonDate: null,
      };
      for (const metric of metrics) {
        row[metric] = values[metric] ?? 0;
      }
      return row;
    });
  }

  return alignPeriodsByRelativeIndex(selectedRange, comparisonRange!).map((day) => {
    const selectedValues = getValuesForDate(day.selectedDate, "selected");
    const comparisonValues = day.comparisonDate
      ? getValuesForDate(day.comparisonDate, "comparison")
      : null;

    const row: ComparisonChartRow = {
      label: day.label,
      name: day.label,
      selectedDate: day.selectedDate,
      comparisonDate: day.comparisonDate,
    };

    for (const metric of metrics) {
      row[metric] = selectedValues[metric] ?? 0;
      row[compareSeriesKey(metric)] = comparisonValues ? (comparisonValues[metric] ?? 0) : 0;
    }

    return row;
  });
}
