import React from "react";
import MLModelsManager from "../components/MLModelsManager";

// The manager owns the page chrome (PageLayout + PageHeader), matching the
// Evaluations page, so this route file is just the entry point.
const MLModels: React.FC = () => <MLModelsManager />;

export default MLModels;
