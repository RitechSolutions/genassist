
import { Home, BarChart2, FileText, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export function MobileNav() {
  const location = useLocation();
  
  const isActive = (path: string) => location.pathname === path;
  
  const items = [
    { icon: Home, label: "Home", path: "/" },
    { icon: FileText, label: "Transcripts", path: "/transcripts" },
    { icon: BarChart2, label: "Analytics", path: "/analytics" },
    { icon: Settings, label: "Settings", path: "/settings" }
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background md:hidden">
      <div className="flex items-center justify-around">
        {items.map(({ icon: Icon, label, path }) => (
          <Link
            key={path}
            to={path}
            className={`flex flex-col items-center py-2 px-4 min-w-[64px] ${
              isActive(path) 
                ? "text-primary" 
                : "text-muted-foreground hover:text-primary"
            }`}
          >
            <Icon className="h-5 w-5" />
            <span className="text-xs mt-1">{label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
