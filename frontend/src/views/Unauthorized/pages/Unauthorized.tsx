import { Lock } from "lucide-react";
import { Button } from "@/components/button";

const UnauthorizedPage = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="text-center bg-white p-8 rounded-lg shadow-xl max-w-lg w-full">
        <p className="text-black font-bold mb-4 text-lg">Unauthorized</p>
        <Lock className="text-gray-500 mb-6 w-12 h-12 mx-auto" />
        <p className="text-xl text-gray-600 mb-6">
          You don't have permission to access this page.
        </p>
        <Button
          onClick={() => (window.location.href = "/dashboard")}
          className="w-full bg-black text-white font-bold hover:bg-black/90"
        >
          Go to Homepage
        </Button>
      </div>
    </div>
  );
};

export default UnauthorizedPage;
