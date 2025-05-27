import { ReactNode } from 'react';

interface MetricCardProps {
  icon: ReactNode;
  value: string | number;
  label: string;
  iconColor?: string;
  className?: string;
}

export function MetricCard({ icon, value, label, iconColor = "text-primary", className = "" }: MetricCardProps) {
  return (
    <div className={`flex flex-col items-center p-3 bg-primary/5 rounded-lg ${className}`}>
      <div className={`w-8 h-8 flex items-center justify-center mb-2 ${iconColor}`}>
        {icon}
      </div>
      <span className="text-lg font-medium">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
} 