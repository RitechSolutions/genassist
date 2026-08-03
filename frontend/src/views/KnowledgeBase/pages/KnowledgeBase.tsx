import React from 'react';
import KnowledgeBaseManager from '../components/KnowledgeBaseManager';
import { useIsMobile } from "@/hooks/useMobile";

const KnowledgeBase: React.FC = () => {
  const isMobile = useIsMobile();

  return (
    <>
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          <KnowledgeBaseManager />
        </div>
      </div>
    </>
  );
};

export default KnowledgeBase; 