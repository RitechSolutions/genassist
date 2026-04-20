import type { NodeHelpContent } from "../../types/nodes";

export const TOOLS_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Tools nodes allow workflows to query systems, execute logic, retrieve knowledge, and run technical operations. They are typically used when your flow needs to interact with external data, code execution, or specialized utility functions.",
  sections: [
    {
      title: "When To Use Tools Nodes",
      body: "Use tools nodes when you need to:",
      bullets: [
        "Call APIs and external services",
        "Query structured or unstructured knowledge",
        "Run SQL, Python, or model inference",
        "Execute utility workflows from within another workflow",
        "Extend automation with technical actions",
      ],
    },
    {
      title: "Summary",
      body: "Tools nodes are ideal when your workflow needs direct action beyond plain data formatting or language generation.",
    },
  ],
};

export const API_CONNECTOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The API Connector node sends requests to external APIs and returns the response to your workflow. It is useful for connecting business systems, services, and data sources through HTTP-based integrations.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the API Connector node when you need to:",
      bullets: [
        "Call external REST APIs",
        "Send or retrieve data from services",
        "Trigger remote operations",
        "Bring third-party data into a workflow",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure API Connector dialog will open.",
        "Enter the Node Name.",
        "Enter the Endpoint URL for the API request.",
        "Choose the HTTP Method.",
        "Add any required Headers and Parameters.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const OPENAPI_EXPLORER_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The OpenAPI Explorer node helps explore and work with OpenAPI-based services inside a workflow. It can be used to inspect available operations, test requests, and integrate documented API capabilities in a guided way.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the OpenAPI Explorer node when you need to:",
      bullets: [
        "Explore available operations from an OpenAPI definition",
        "Inspect API endpoints before connecting them to a workflow",
        "Test request structures and inputs",
        "Understand how a documented service can be used in your automation",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure OpenAPI Explorer dialog will open.",
        "Enter the Node Name.",
        "Select or load the OpenAPI specification you want to explore.",
        "Review the available endpoints or operations.",
        "Configure the request details you want to inspect or test.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const KNOWLEDGE_QUERY_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Knowledge Query node retrieves information from a connected knowledge source. It is used when workflows need to search documents, reference content, or fetch grounded answers from stored knowledge.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Knowledge Query node when you need to:",
      bullets: [
        "Search a knowledge base",
        "Retrieve document-based context",
        "Support grounded AI responses",
        "Fetch relevant information for later workflow steps",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Knowledge Query dialog will open.",
        "Enter the Node Name.",
        "Enter the Query you want to run.",
        "Set the Limit and decide whether to Force limit.",
        "Select the Knowledge Bases that should be queried.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const SQL_EXECUTOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The SQL Executor node runs SQL queries against a selected data source. It is useful when you want to query relational data directly inside a workflow.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the SQL Executor node when you need to:",
      bullets: [
        "Query relational databases",
        "Select a data source and run SQL against it",
        "Switch between different query modes",
        "Feed workflow steps with structured database results",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure SQL Executor dialog will open.",
        "Enter the Node Name.",
        "Select the Data Source to query.",
        "Choose the Mode used to provide the SQL query.",
        "Review any parameters or query inputs required by that mode.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const ML_MODEL_INFERENCE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The ML Model Inference node sends input data to a machine learning model and returns the prediction or inference result. It is used when workflows need model-based decisions outside of general language tasks.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the ML Model Inference node when you need to:",
      bullets: [
        "Classify or score records",
        "Run predictive models on workflow data",
        "Enrich workflows with inference results",
        "Connect operational flows to trained ML services",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure ML Model dialog will open.",
        "Select the ML Model to run.",
        "Configure the inference parameters shown for that model.",
        "Review the input fields expected by the selected model.",
        "Confirm how the prediction output will be used downstream.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const PYTHON_EXECUTOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Python Executor node runs Python logic as part of a workflow. It is useful for custom transformations, calculations, data processing, or specialized operations that are easier to express in code.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Python Executor node when you need to:",
      bullets: [
        "Run custom processing logic",
        "Perform calculations or data manipulation",
        "Parse complex data structures",
        "Extend workflows with scripted behavior",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Python Executor dialog will open.",
        "Enter the Node Name.",
        "Add the Python Code or generate a starter template.",
        "Use the available workflow variables through the params input.",
        "Store the final output in the expected result variable and review the available execution notes.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const THREAD_RAG_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Thread RAG node retrieves relevant context from thread history or conversation data to support downstream reasoning and grounded responses. It is useful for workflows that rely on prior interactions.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Thread RAG node when you need to:",
      bullets: [
        "Retrieve context from prior conversation history",
        "Ground responses in earlier thread content",
        "Support long-running assistants",
        "Improve continuity across workflow steps",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Thread RAG dialog will open.",
        "Enter the Node Name.",
        "Select the Action to perform.",
        "Enter the Query and configure the Top K retrieval limit.",
        "Review the vector store and text embedding configuration used for retrieval.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const WORKFLOW_EXECUTOR_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Workflow Executor node triggers another workflow or reusable flow segment from within the current workflow. It is useful for modular automation, reuse, and separation of responsibilities.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Workflow Executor node when you need to:",
      bullets: [
        "Reuse existing workflows",
        "Break large automations into smaller modules",
        "Trigger child workflows",
        "Centralize shared business logic",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Workflow Executor dialog will open.",
        "Enter the Node Name.",
        "Select the Workflow you want this node to execute.",
        "Configure the input parameters required by the selected workflow.",
        "Review the values that will be passed into the child workflow.",
        "Save the node configuration.",
      ],
    },
  ],
};
