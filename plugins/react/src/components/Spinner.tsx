import React from 'react';
import { Loader2 } from 'lucide-react';

export interface SpinnerProps {
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 18, color = '#000', style }) => {
  const spinKeyframes = `
    @keyframes ga_spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  `;
  return (
    <>
      <style>{spinKeyframes}</style>
      <Loader2 size={size} color={color} style={{ animation: 'ga_spin 1s linear infinite', ...style }} />
    </>
  );
};

