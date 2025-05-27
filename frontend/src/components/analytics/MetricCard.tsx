import { Card } from "@/components/card";
import { Area, AreaChart, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { LucideIcon, InfoIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  data: Array<{ name: string; value: number }>;
  color: string;
  format: (value: number) => string;
  description?: string;
}

export const MetricCard = ({ 
  title, 
  value, 
  icon: Icon, 
  data, 
  color, 
  format,
  description
}: MetricCardProps) => {
  return (
    <Card className="p-4 sm:p-6 shadow-sm transition-shadow hover:shadow-md animate-fade-up bg-white">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 sm:w-5 sm:h-5" style={{ color }} />
          <h3 className="text-sm sm:text-base font-medium">{title}</h3>
          {description && (
            <div className="relative group">
              <InfoIcon className="w-3.5 h-3.5 text-gray-400 cursor-help" />
              <div className="absolute z-10 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-gray-800 text-white text-xs rounded shadow-lg">
                {description}
                <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-800"></div>
              </div>
            </div>
          )}
        </div>
        {/* <span className={`text-xs font-medium ${
          trend.startsWith('+') ? 'text-green-500' : 'text-red-500'
        }`}>
          {trend}
        </span> */}
      </div>
      <p className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">{value}</p>
      <div className="h-[80px] sm:h-[100px] w-[calc(100%+32px)] sm:w-[calc(100%+48px)] -ml-4 sm:-ml-6 -mb-4 sm:-mb-6">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ left: 0, right: -8, top: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`color${title.replace(/\s+/g, '')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.1}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <RechartsTooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-white p-2 rounded-lg shadow-lg border text-xs sm:text-sm">
                      <p className="font-medium">
                        {format(payload[0].value as number)}
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              fill={`url(#color${title.replace(/\s+/g, '')})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
