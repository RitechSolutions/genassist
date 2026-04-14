import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";

/** User-facing job title: suffix (name), then output path basename, then base model, then id. */
export function getLocalFineTuneJobDisplayName(job: LocalFineTuneJob): string {
  const suf = job.suffix?.trim();
  if (suf) return suf;
  const tail = job.fine_tuned_model?.split("/").pop()?.trim();
  if (tail) return tail;
  return job.model?.trim() || job.id || "—";
}

/** Subtitle under the name (e.g. base model) when it adds context. */
export function getLocalFineTuneJobNameSubtitle(
  job: LocalFineTuneJob,
  primary: string
): string | null {
  const model = job.model?.trim();
  if (!model || model === primary) return null;
  return model;
}
