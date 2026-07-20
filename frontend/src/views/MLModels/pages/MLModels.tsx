import React from 'react';
import MLModelsManager from '../components/MLModelsManager';
import { useIsMobile } from "@/hooks/useMobile";

const MLModels: React.FC = () => {
  const isMobile = useIsMobile();

  return (
    <>
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          <MLModelsManager />
        </div>
      </div>
    </>
  );
};

export default MLModels;

