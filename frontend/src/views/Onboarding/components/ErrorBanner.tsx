interface ErrorBannerProps {
  message: string | null;
}

export const ErrorBanner = ({ message }: ErrorBannerProps) => {
  if (!message) return null;
  return (
    <div className="w-full max-w-2xl text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-2.5 text-center">
      {message}
    </div>
  );
};
