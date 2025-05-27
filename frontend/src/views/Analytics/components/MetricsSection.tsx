import { MetricCard } from "@/components/analytics/MetricCard";
import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { Timer, SmileIcon, Award, CheckCircle } from "lucide-react";
import { generateTimeData } from "../helpers/timeDataGenerator";
import { generateMetricData } from "../helpers/metricDataGenerator";
import { MetricsAPIResponse } from "@/interfaces/analytics.interface";

interface MetricsSectionProps {
  timeFrame: string;
  metrics: MetricsAPIResponse | null;
  loading: boolean;
  error: Error | null;
}

export const MetricsSection = ({ timeFrame, metrics, loading, error }: MetricsSectionProps) => {
  const defaultMetrics = {
    "Customer Satisfaction": "0%",
    "Resolution Rate": "0%",
    "Positive Sentiment": "0%",
    "Neutral Sentiment": "0%",
    "Negative Sentiment": "0%",
    "Efficiency": "0%",
    "Response Time": "0%",
    "Quality of Service": "0%",
    "total_analyzed_audios": 0,
  };

  const formattedData = metrics || defaultMetrics;

  const metricCards = [
    {
      title: "Response Time",
      value: formattedData["Response Time"],
      trend: "-12%",
      icon: Timer,
      data: generateMetricData(timeFrame, parseFloat(formattedData["Response Time"]), 1).map(item => ({
        name: "Response Time", value: item.value
      })),
      color: "#3b82f6",
      format: (value: number) => `${value.toFixed(1)}%`,
    },
    {
      title: "Customer Satisfaction",
      value: formattedData["Customer Satisfaction"],
      trend: "+5%",
      icon: SmileIcon,
      data: generateMetricData(timeFrame, parseFloat(formattedData["Customer Satisfaction"]), 10).map(item => ({
        name: "Customer Satisfaction", value: item.value
      })),
      color: "#10b981",
      format: (value: number) => `${value.toFixed(1)}%`,
    },
    {
      title: "Quality of Service",
      value: formattedData["Quality of Service"],
      trend: "+0.3%",
      icon: Award,
      data: generateMetricData(timeFrame, parseFloat(formattedData["Quality of Service"]), 0.5).map(item => ({
        name: "Quality of Service", value: item.value
      })),
      color: "#8b5cf6",
      format: (value: number) => `${value.toFixed(1)}%`,
    },
    {
      title: "Resolution Rate",
      value: formattedData["Resolution Rate"],
      trend: "+8%",
      icon: CheckCircle,
      data: generateMetricData(timeFrame, parseFloat(formattedData["Resolution Rate"]), 8).map(item => ({
        name: "Resolution Rate", value: item.value
      })),
      color: "#f59e0b",
      format: (value: number) => `${value.toFixed(1)}%`,
    },
  ];

  if (loading) {
    return <div className="text-center py-8">Loading analytics data...</div>;
  }

  if (error) {
    return <div className="text-center py-8 text-red-500">Error loading analytics data</div>;
  }

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 mb-6 sm:mb-8">
        {metricCards.map((metric) => (
          <MetricCard key={metric.title} {...metric} />
        ))}
      </div>

      <PerformanceChart timeSeriesData={generateTimeData(timeFrame)} />
    </>
  );
}; 