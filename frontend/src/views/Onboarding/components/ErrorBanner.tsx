interface ErrorBannerProps {
  message: string | null;
}

export const ErrorBanner = ({ message }: ErrorBannerProps) => {
  if (!message) return null;
  return (
    <div className="w-full max-w-2xl text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2">
      {message}
    </div>
  );
};