import { TimeDataPoint } from "@/interfaces/analytics.interface";

export const generateTimeData = (timeFrame: string): TimeDataPoint[] => {
  const data: TimeDataPoint[] = [];
  const now = new Date();
  
  let count: number;
  let interval: number;
  let format: (date: Date) => string;
  
  switch (timeFrame) {
    case 'today':
      count = 24;
      interval = 60 * 60 * 1000;
      format = (date) => date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      break;
    case '7days':
      count = 7;
      interval = 24 * 60 * 60 * 1000;
      format = (date) => date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      break;
    case '30days':
      count = 30;
      interval = 24 * 60 * 60 * 1000;
      format = (date) => date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      break;
    case '6months':
      count = 6;
      interval = 30 * 24 * 60 * 60 * 1000;
      format = (date) => date.toLocaleDateString([], { month: 'short', year: '2-digit' });
      break;
    case '12months':
      count = 12;
      interval = 30 * 24 * 60 * 60 * 1000;
      format = (date) => date.toLocaleDateString([], { month: 'short', year: '2-digit' });
      break;
    default:
      count = 7;
      interval = 24 * 60 * 60 * 1000;
      format = (date) => date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }
  
  for (let i = count - 1; i >= 0; i--) {
    const date = new Date(now.getTime() - (i * interval));
    
    data.push({
      date: format(date),
      value: 70 + Math.random() * 20,
    });
  }
  
  return data;
}; 