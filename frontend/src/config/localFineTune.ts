/**
 * Base URL for the local fine-tuning server.
 * Configure via VITE_LOCAL_FINE_TUNE_API_URL in frontend/.env.
 */
const normalizeLocalFineTuneUrl = (url: string): string =>
  url.endsWith("/") ? url : `${url}/`;

export const getLocalFineTuneApiUrl = (): string => {
  const url = import.meta.env.VITE_LOCAL_FINE_TUNE_API_URL;

  if (typeof url !== "string" || url.trim() === "") {
    throw new Error(
      "Missing VITE_LOCAL_FINE_TUNE_API_URL. Set it in frontend/.env."
    );
  }

  return normalizeLocalFineTuneUrl(url.trim());
};
