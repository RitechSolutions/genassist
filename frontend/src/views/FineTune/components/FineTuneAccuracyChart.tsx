import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/chart";
import { AccuracyPoint } from "../types";

interface FineTuneAccuracyChartProps {
  title?: string;
  data: AccuracyPoint[];
  emptyLabel?: string;
  className?: string;
}

const chartConfig: ChartConfig = {
  accuracy: {
    label: "Accuracy",
    color: "var(--color-accuracy, hsl(var(--primary)))",
  },
};

export function FineTuneAccuracyChart({
  title = "Accuracy over time",
  data,
  emptyLabel = "Data N/A",
  className,
}: FineTuneAccuracyChartProps) {
  const series = data.map((p) => ({
    label: p.label,
    accuracy: p.value,
  }));

  return (
    <div className={`rounded-lg p-4 bg-white ${className || ""}`}>
      <div className="text-sm font-semibold mb-3">{title}</div>
      <div className="h-[240px] relative">
        {series.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            {emptyLabel}
          </div>
        ) : (
          <ChartContainer config={chartConfig} className="!aspect-auto h-full w-full">
          <LineChart
            data={series}
            margin={{
              left: 12,
              right: 12,
                top: 8,
                bottom: 8,
              }}
            >
              <CartesianGrid vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="label"
                interval={0}
                minTickGap={0}
                padding={{ left: 12, right: 12 }}
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                tick={{ fill: "#9ca3af", fontSize: 12 }}
              />
              <YAxis
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickLine={false}
                axisLine={false}
                tickFormatter={() => ""}
                width={0}
              />
              <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
              <Line
                type="natural"
                dataKey="accuracy"
                name="Accuracy"
                stroke="#2A9D90"
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ChartContainer>
        )}
      </div>
    </div>
  );
}
