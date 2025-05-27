import { BarChart3 } from "lucide-react";

interface SentimentDistributionProps {
  positive: number;
  neutral: number;
  negative: number;
}

export function SentimentDistribution({ positive = 0, neutral = 0, negative = 0 }: SentimentDistributionProps) {
  const total = positive + neutral + negative || 1;

  const sentiments = [
    { name: "Positive", value: (positive / total) * 100, color: "bg-green-500", textColor: "text-green-600" },
    { name: "Neutral", value: (neutral / total) * 100, color: "bg-yellow-500", textColor: "text-yellow-600" },
    { name: "Negative", value: (negative / total) * 100, color: "bg-red-500", textColor: "text-red-600" }
  ];

  return (
    <div className="bg-primary/5 p-4 rounded-lg">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Sentiment Distribution
      </h3>
      <div className="flex gap-4">
        {sentiments.map((sentiment, idx) => (
          <div key={idx} className="flex-1">
            <div className="flex justify-between text-sm mb-1">
              <span className={`${sentiment.textColor} capitalize`}>
                {sentiment.name}
              </span>
              <span>{Math.round(sentiment.value)}%</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full">
              <div
                className={`h-full ${sentiment.color} rounded-full`}
                style={{ width: `${Math.max(sentiment.value, 2)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
