export const generateTimeData = (timeFrame: string) => {
  switch (timeFrame) {
    case 'today':
      return Array.from({ length: 24 }, (_, i) => ({
        name: `${i}:00`,
        value: 80 + Math.random() * 20
      }));
    case '7days':
      return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => ({
        name: day,
        value: 80 + Math.random() * 20
      }));
    case '30days':
      return Array.from({ length: 30 }, (_, i) => ({
        name: `Day ${i + 1}`,
        value: 80 + Math.random() * 20
      }));
    case '6months':
      return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map(month => ({
        name: month,
        value: 80 + Math.random() * 20
      }));
    case '12months':
      return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map(month => ({
        name: month,
        value: 80 + Math.random() * 20
      }));
    default:
      return [];
  }
};

export const generateMetricData = (timeFrame: string, baseValue: number, variance: number) => {
  const length = timeFrame === 'today' ? 24 : 
                timeFrame === '7days' ? 7 :
                timeFrame === '30days' ? 30 :
                timeFrame === '6months' ? 6 : 12;

  return Array.from({ length }, (_, i) => ({
    name: i.toString(),
    value: baseValue + (Math.random() - 0.5) * variance
  }));
};
