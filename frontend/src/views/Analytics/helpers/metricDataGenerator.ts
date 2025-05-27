export interface MetricDataPoint {
  date: string;
  value: number;
}

export const generateMetricData = (
  timeFrame: string,
  baseValue: number,
  volatility: number
): MetricDataPoint[] => {
  const data: MetricDataPoint[] = [];
  let points = 10;
  
  switch (timeFrame) {
    case 'today':
      points = 24;
      break;
    case '7days':
      points = 7;
      break;
    case '30days':
      points = 30;
      break;
    case '6months':
      points = 6;
      break;
    case '12months':
      points = 12;
      break;
    default:
      points = 10;
  }
  
  const formatDate = (i: number): string => {
    if (timeFrame === 'today') {
      return `${i}:00`;
    } else if (timeFrame === '7days' || timeFrame === '30days') {
      return `Day ${i+1}`;
    } else {
      return `Month ${i+1}`;
    }
  };
  
  for (let i = 0; i < points; i++) {
    const fluctuation = (Math.random() * 2 - 1) * volatility;
    const value = Math.max(0, baseValue + fluctuation);
    
    data.push({
      date: formatDate(i),
      value: value
    });
  }
  
  return data;
}; 