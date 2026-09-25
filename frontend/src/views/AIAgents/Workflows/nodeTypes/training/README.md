# Training Nodes

This directory contains nodes related to machine learning training workflows.

## Available Training Nodes

### 1. TrainDataSource Node
Fetches training data from databases or CSV files.

**Features:**
- **Data Source Method**: Query TimeDB, Snowflake, PostgreSQL, MySQL, TimescaleDB
- **CSV Upload Method**: Upload CSV files directly to server
- **Variable Substitution**: Use `{{variable}}` syntax in SQL queries
- **File Management**: Server-side file storage and validation

**Configuration:**
- `sourceType`: "datasource" or "csv"
- `dataSourceId`: Database connection ID
- `query`: SQL query with variable support
- `csvFilePath`: Server path to uploaded CSV file

### 2. PreprocessingNode
Transforms and cleans training data using Python.

**Features:**
- **Python Code Editor**: Full Python environment for data preprocessing
- **Column Management**: Define expected input/output columns
- **Parameter Support**: Pass dynamic parameters to preprocessing code
- **Template Code**: Pre-built preprocessing templates

**Configuration:**
- `pythonCode`: Python code for data transformation
- `inputColumns`: Expected input column names
- `outputColumns`: Expected output column names
- `parameters`: Dynamic parameters for the code

**Template Features:**
- Handle missing values
- Remove duplicates
- Feature engineering
- Data scaling and normalization

### 3. TrainModelNode
Trains machine learning models on preprocessed data.

**Features:**
- **Multiple Algorithms**: XGBoost, Random Forest, Linear/Logistic Regression, Neural Networks
- **Auto-Detection**: Automatically detects classification vs regression
- **Parameter Tuning**: Model-specific parameter configuration
- **Validation Split**: Configurable train/validation split
- **Custom Code**: Override default training with custom Python code

**Configuration:**
- `modelType`: Algorithm to use (xgboost, random_forest, etc.)
- `targetColumn`: Target variable column name
- `featureColumns`: List of feature column names
- `modelParameters`: Model-specific hyperparameters
- `validationSplit`: Fraction for validation (0.1-0.5)
- `pythonCode`: Optional custom training code

## Workflow Example

```
TrainDataSource → PreprocessingNode → TrainModelNode
```

1. **TrainDataSource**: Fetch data from database or CSV
2. **PreprocessingNode**: Clean and transform the data
3. **TrainModelNode**: Train ML model on processed data

## Node Connections

- **TrainDataSource**: Output → PreprocessingNode Input
- **PreprocessingNode**: Output → TrainModelNode Input
- **TrainModelNode**: Output → Model storage/inference nodes

## Color Coding

- **TrainDataSource**: Cyan theme
- **PreprocessingNode**: Orange theme  
- **TrainModelNode**: Purple theme

## Future Enhancements

- **Data Validation**: Schema validation and data quality checks
- **Feature Selection**: Automated feature selection algorithms
- **Hyperparameter Tuning**: Grid search and Bayesian optimization
- **Model Comparison**: Side-by-side model performance comparison
- **AutoML**: Automated model selection and training
- **Model Versioning**: Track and manage model versions
- **Deployment**: Direct model deployment to inference endpoints

