import type { LocalFineTuneJobEvent } from "@/interfaces/localFineTune.interface";
import type { StepDataPoint } from "@/views/FineTune/components/AccuracyOverStepsChart";

/** In-order loss points from "Training metrics" events (step logging). */
export function buildLossSeriesFromEvents(
  events: LocalFineTuneJobEvent[]
): StepDataPoint[] {
  let step = 0;
  const points: StepDataPoint[] = [];
  for (const e of events) {
    if (e.message !== "Training metrics" || e.data == null) continue;
    const d = e.data as Record<string, unknown>;
    const raw = d.loss ?? d.train_loss;
    const loss = typeof raw === "number" ? raw : Number(raw);
    if (!isFinite(loss)) continue;
    step += 1;
    points.push({ label: `Step ${step}`, value: loss });
  }
  return points;
}

export function parseTrainSampleCount(
  events: LocalFineTuneJobEvent[]
): number | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.message !== "Datasets loaded and formatted" || !e.data) continue;
    const n = (e.data as Record<string, unknown>).train_samples;
    const num = typeof n === "number" ? n : Number(n);
    if (isFinite(num)) return num;
  }
  return null;
}

export function parseFinalTrainLoss(
  events: LocalFineTuneJobEvent[]
): number | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.message !== "Training metrics" || !e.data) continue;
    const d = e.data as Record<string, unknown>;
    if (d.train_loss != null) {
      const v = typeof d.train_loss === "number" ? d.train_loss : Number(d.train_loss);
      if (isFinite(v)) return v;
    }
  }
  return null;
}
