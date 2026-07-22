import { Lock } from "lucide-react";
import { Button } from "@/components/button";

const UnauthorizedPage = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-muted">
      <div className="text-center bg-card p-8 rounded-lg shadow-xl max-w-lg w-full">
        <p className="text-foreground font-bold mb-4 text-lg">Unauthorized</p>
        <Lock className="text-muted-foreground mb-6 w-12 h-12 mx-auto" />
        <p className="text-xl text-muted-foreground mb-6">
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
