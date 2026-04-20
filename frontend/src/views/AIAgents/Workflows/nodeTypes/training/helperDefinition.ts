import type { NodeHelpContent } from "../../types/nodes";

export const TRAINING_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Training nodes support workflows related to preparing data and training machine learning models. They are used when your project includes model development pipelines in addition to inference or automation flows.",
  sections: [
    {
      title: "When To Use Training Nodes",
      body: "Use training nodes when you need to:",
      bullets: [
        "Collect or define training data sources",
        "Prepare raw data for model training",
        "Launch or manage model training steps",
        "Build repeatable ML pipeline workflows",
      ],
    },
    {
      title: "Summary",
      body: "Training nodes are a good fit for teams that want to operationalize the process of creating and updating models.",
    },
  ],
};

export const TRAIN_DATA_SOURCE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Train Data Source node defines the data source used for model training. It is responsible for connecting training workflows to the raw or prepared data needed for model development.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Train Data Source node when you need to:",
      bullets: [
        "Select data for a training pipeline",
        "Connect training flows to source datasets",
        "Define the starting point for model preparation",
        "Standardize training data inputs",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Train Data Source dialog will open.",
        "Enter the Node Name.",
        "Select the Data Source type to use for training input.",
        "Upload or connect the training file or datasource.",
        "Review the dataset that will be passed to downstream training steps.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const DATA_PREPROCESSING_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Data Preprocessing node cleans and prepares training data before model training. It is used to transform raw input into a format that supports better learning and more reliable model performance.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Data Preprocessing node when you need to:",
      bullets: [
        "Clean raw training data",
        "Normalize or transform features",
        "Prepare datasets for training",
        "Apply repeatable preprocessing logic",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Data Preprocessing dialog will open.",
        "Enter the Node Name.",
        "Provide the File URL and analyze the dataset.",
        "Choose whether to configure preprocessing visually or in code.",
        "Add and review the preprocessing steps that should run in order.",
        "Save the node configuration.",
      ],
    },
  ],
};

export const TRAIN_MODEL_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Train Model node runs the model training process using prepared data and selected training settings. It is used to launch repeatable training workflows and produce updated model artifacts.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Train Model node when you need to:",
      bullets: [
        "Launch model training jobs",
        "Create updated model versions",
        "Automate parts of the ML lifecycle",
        "Build repeatable training pipelines",
      ],
    },
    {
      title: "Configuring the node",
      steps: [
        "Click the settings icon in the node header.",
        "The Configure Train Model dialog will open.",
        "Enter the Node Name.",
        "Provide the File URL and analyze the dataset.",
        "Select the Model Type, Target Column, and Feature Columns.",
        "Adjust the Validation Split and review the final training setup.",
        "Save the node configuration.",
      ],
    },
  ],
};
