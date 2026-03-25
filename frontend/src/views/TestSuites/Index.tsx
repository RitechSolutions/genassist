import React from "react";
import { Navigate } from "react-router-dom";

const TestSuitesIndex: React.FC = () => {
  return <Navigate to="/tests/datasets" replace />;
};

export default TestSuitesIndex;

