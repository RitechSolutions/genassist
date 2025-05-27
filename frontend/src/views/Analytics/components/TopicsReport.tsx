import { useState, useEffect } from 'react';
import { Card } from '@/components/card';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { fetchTopicsReport } from '@/services/metrics';
import { ChartDataItem } from '@/interfaces/analytics.interface';
import { CardHeader } from '@/components/CardHeader';
import { getTopicColorMap } from '../utils/topicsColors';


export function TopicsReport() {
  const [data, setData] = useState<ChartDataItem[]>([]);
  const [totalConversations, setTotalConversations] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [colorMap, setColorMap] = useState<Record<string, string>>({});

  useEffect(() => {
    const getReportData = async () => {
      setLoading(true);
      setError(null);
      try {
        const reportData = await fetchTopicsReport();
        if (reportData && reportData.details) {
          const chartData = Object.entries(reportData.details).map(([key, value]) => ({
            name: key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase()),
            value,
            originalKey: key,
          }));
          setData(chartData);
          setTotalConversations(reportData.total);

          const topics = chartData.map((item) => item.originalKey);
          const map = getTopicColorMap(topics);
          setColorMap(map);
        } else {
          setData([]);
          setTotalConversations(0);
        }
      } catch (err) {
        setError('Failed to load topics report. Please try again.');
        setData([]);
        setTotalConversations(0);
      } finally {
        setLoading(false);
      }
    };

    getReportData();
  }, []);

  return (
    <Card className="p-6 shadow-sm transition-shadow hover:shadow-md animate-fade-up bg-white h-full">
      <CardHeader 
        title="Conversations by type"
        tooltipText="Breakdown of conversations by their identified topics or types."
      />

      {loading ? (
        <div className="flex justify-center items-center h-[320px]">
          <p className="text-muted-foreground">Loading report...</p>
        </div>
      ) : error ? (
        <div className="flex justify-center items-center h-[320px]">
          <p className="text-red-500">{error}</p>
        </div>
      ) : data.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              outerRadius={125}
              innerRadius={80}
              fill="#8884d8"
              dataKey="value"
              strokeWidth={0}
            >
              {data.map((entry, index) => {
                const color = colorMap[entry.originalKey];
                return (
                  <Cell key={`cell-${index}`} fill={color} stroke={color} strokeWidth={2} />
                );
              })}
            </Pie>
            <Tooltip formatter={(value: number, name: string) => [value, name.charAt(0).toUpperCase() + name.slice(1)]} />
            <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="text-2xl font-semibold">
              {totalConversations}
            </text>
            <text x="50%" y="50%" dy={22} textAnchor="middle" dominantBaseline="central" className="text-xs text-muted-foreground">
              Conversations
            </text>
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex justify-center items-center h-[320px]">
          <p className="text-muted-foreground">No data available for topics report.</p>
        </div>
      )}
    </Card>
  );
} 