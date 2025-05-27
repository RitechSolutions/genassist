export interface TopicsReportResponse {
  total: number;
  details: {
    [key: string]: number;
  };
}

export interface MetricsDataPoint {
  name: string;
  satisfaction: number;
  serviceQuality: number;
  resolutionRate: number;
}

export interface MetricsAPIResponse {
  data: MetricsDataPoint[]; 
}

export interface TimeDataPoint {
  date: string;
  value: number;
}

export interface MetricDataPoint {
  value: number;
  timestamp: string;
} 

export interface ChartDataItem {
  name: string;
  value: number;
  originalKey: string;
}