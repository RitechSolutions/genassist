import { useState, useEffect } from "react";
import { Card } from "@/components/card";
import { Area, AreaChart, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { fetchMetrics } from "@/services/metrics";
import { format, subDays } from "date-fns";
import { MetricsData } from "@/interfaces/metrics.interface";

interface PerformanceChartProps {
  timeFilter?: string;
}

export const PerformanceChart = ({ timeFilter }: PerformanceChartProps) => {
  const [data, setData] = useState<
    Array<{ name: string; satisfaction: number; serviceQuality: number; resolutionRate: number }>
  >([]);

  useEffect(() => {
    const getMetrics = async () => {
      try {
        const metrics: MetricsData | null = await fetchMetrics();

        if (metrics && metrics.metrics) {
          const last7Days = [...Array(7)].map((_, i) => {
            const date = subDays(new Date(), 6 - i);
            const formattedDate = format(date, "EEE");

            const entry = metrics.metrics.find((e) => e.date === formattedDate) || {};
            return {
              name: formattedDate,
              satisfaction: parseFloat(entry["Customer Satisfaction"]) || 50,
              serviceQuality: parseFloat(entry["Quality of Service"]) || 50,
              resolutionRate: parseFloat(entry["Resolution Rate"]) || 50,
            };
          });

          setData(last7Days);
        } else {
          setData(sampleData);
        }
      } catch (error) {
        setData(sampleData);
      }
    };

    getMetrics();
  }, []);

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-white">
      <h2 className="text-base sm:text-lg font-semibold mb-4">Weekly Performance Trend</h2>
      <div className="h-[300px] sm:h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorSatisfaction" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorServiceQuality" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#9333ea" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#9333ea" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorResolutionRate" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#dc2626" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
              </linearGradient>
            </defs>

            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#666", fontSize: 10, dy: 10 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, 100]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#666", fontSize: 10 }}
              width={35}
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fff",
                border: "none",
                borderRadius: "8px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                fontSize: "12px",
              }}
              formatter={(value: number) => [`${value}%`, "Value"]}
            />

            <Area type="monotone" dataKey="satisfaction" stroke="#16a34a" strokeWidth={2} fill="url(#colorSatisfaction)" />
            <Area type="monotone" dataKey="serviceQuality" stroke="#9333ea" strokeWidth={2} fill="url(#colorServiceQuality)" />
            <Area type="monotone" dataKey="resolutionRate" stroke="#dc2626" strokeWidth={2} fill="url(#colorResolutionRate)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};

const sampleData = [
  { name: "Mon", satisfaction: 76, serviceQuality: 68, resolutionRate: 50 },
  { name: "Tue", satisfaction: 80, serviceQuality: 70, resolutionRate: 55 },
  { name: "Wed", satisfaction: 78, serviceQuality: 69, resolutionRate: 53 },
  { name: "Thu", satisfaction: 82, serviceQuality: 72, resolutionRate: 58 },
  { name: "Fri", satisfaction: 75, serviceQuality: 65, resolutionRate: 48 },
  { name: "Sat", satisfaction: 79, serviceQuality: 67, resolutionRate: 52 },
  { name: "Sun", satisfaction: 81, serviceQuality: 71, resolutionRate: 57 },
];
