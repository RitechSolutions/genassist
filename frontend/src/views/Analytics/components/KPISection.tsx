import { useState, useEffect } from "react";
import { Clock, ThumbsUp, Award, CheckCircle } from "lucide-react";
import { fetchMetrics } from "@/services/metrics";
import { generateMetricData } from "../helpers/metricDataGenerator";
import { MetricsAPIResponse } from "@/interfaces/analytics.interface";
import { MetricCard } from "@/components/analytics/MetricCard";

import { usePermissions, useIsLoadingPermissions } from "@/context/PermissionContext";

interface KPISectionProps {
  timeFilter: string;
}

export function KPISection({ timeFilter }: KPISectionProps) {
  const permissions = usePermissions();
  const isLoadingPermissions = useIsLoadingPermissions();
  const [metrics, setMetrics] = useState<MetricsAPIResponse | null>(null);

  useEffect(() => {
    const getMetrics = async () => {
      if (isLoadingPermissions) {
        return;
      }
      if (permissions.includes("read:metrics") || permissions.includes("*") ) {
        try {
          const data = await fetchMetrics();
          console.log(data );
          setMetrics(data);
        } catch (err) {
          console.log(err)
        }
      }
    };
  
    getMetrics();
  }, [isLoadingPermissions, permissions]);

  const defaultMetrics = {
    "Response Time": "0m",
    "Customer Satisfaction": "0%",
    "Quality of Service": "0%",
    "Resolution Rate": "0%",
    "Efficiency": "0%",
  };

  const formattedData = metrics || defaultMetrics;

  const kpiMetrics = [
    {
      title: "Responsiveness",
      value: formattedData["Response Time"],
      icon: Clock,
      color: "#3b82f6",
      data: generateMetricData(timeFilter, parseFloat(formattedData["Response Time"]) || 0, 0.5).map(item => ({
        name: item.date, 
        value: item.value
      })),
      format: (value: number) => `${value.toFixed(1)}m`,
      tooltip: "Average time it takes for agents to respond to customer inquiries",
    },
    {
      title: "Satisfaction",
      value: formattedData["Customer Satisfaction"],
      icon: ThumbsUp,
      color: "#16a34a",
      data: generateMetricData(timeFilter, parseFloat(formattedData["Customer Satisfaction"]) || 0, 5).map(item => ({
        name: item.date, 
        value: item.value
      })),
      format: (value: number) => `${value.toFixed(1)}%`,
      tooltip: "Percentage of customers reporting a positive experience with our service",
    },
    {
      title: "Service Quality",
      value: formattedData["Quality of Service"],
      icon: Award,
      color: "#9333ea",
      data: generateMetricData(timeFilter, parseFloat(formattedData["Quality of Service"]) || 0, 0.3).map(item => ({
        name: item.date, 
        value: item.value
      })),
      format: (value: number) => `${value.toFixed(1)}%`,
      tooltip: "Measure of service performance based on internal quality standards",
    },
    {
      title: "Resolution Rate",
      value: formattedData["Resolution Rate"],
      icon: CheckCircle,
      color: "#dc2626",
      data: generateMetricData(timeFilter, parseFloat(formattedData["Resolution Rate"]) || 0, 3).map(item => ({
        name: item.date, 
        value: item.value
      })),
      format: (value: number) => `${value.toFixed(1)}%`,
      tooltip: "Percentage of customer issues resolved on first contact",
    },
  ];

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      {kpiMetrics.map((metric) => (
        <MetricCard 
          key={metric.title}
          title={metric.title}
          value={metric.value}
          icon={metric.icon}
          data={metric.data}
          color={metric.color}
          format={metric.format}
          description={metric.tooltip}
        />
      ))}
    </section>
  );
} 