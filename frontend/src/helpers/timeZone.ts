export type TimeZoneMode = "utc" | "local";

export const TIME_ZONE_MODE_KEY = "genassist_time_zone";

export function readTimeZoneMode(): TimeZoneMode {
  try {
    return localStorage.getItem(TIME_ZONE_MODE_KEY) === "local"
      ? "local"
      : "utc";
  } catch {
    return "utc";
  }
}

export function writeTimeZoneMode(mode: TimeZoneMode): void {
  try {
    localStorage.setItem(TIME_ZONE_MODE_KEY, mode);
  } catch {
    // Storage may be blocked; reads then fall back to UTC.
  }
}

/** `timeZone` option for Intl formatters; undefined means the browser zone. */
export function displayTimeZone(): "UTC" | undefined {
  return readTimeZoneMode() === "utc" ? "UTC" : undefined;
}

export function localTimeZoneName(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Calendar fields of an instant in the active zone; month is 0-based. */
export function dateParts(date: Date) {
  if (readTimeZoneMode() === "local") {
    return {
      year: date.getFullYear(),
      month: date.getMonth(),
      day: date.getDate(),
      hours: date.getHours(),
      minutes: date.getMinutes(),
      seconds: date.getSeconds(),
    };
  }
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth(),
    day: date.getUTCDate(),
    hours: date.getUTCHours(),
    minutes: date.getUTCMinutes(),
    seconds: date.getUTCSeconds(),
  };
}

/** Days since the epoch of the instant's calendar day in the active zone. */
export function calendarDayNumber(date: Date): number {
  const { year, month, day } = dateParts(date);
  return Date.UTC(year, month, day) / 86_400_000;
}
