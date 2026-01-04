import React from "react";
import { GenAgentChat } from "../src";

const BasicExample: React.FC = () => {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        padding: "20px",
        boxSizing: "border-box",
      }}
    >
      <GenAgentChat
        baseUrl="https://api.example.com/"
        apiKey="your-api-key-here"
        tenant="your-tenant-id-here"
        headerTitle="Customer Support"
        placeholder="Ask us anything..."
      />
    </div>
  );
};

export default BasicExample;
