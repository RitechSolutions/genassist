# MCP Test Server

A simple MCP (Model Context Protocol) test server for testing MCP node functionality.

## Features

- Supports both HTTP-based and JSON-RPC MCP protocols
- Multiple test tools: read_file, write_file, list_files, delete_file, echo
- In-memory file storage for testing
- Optional API key authentication (disabled for testing)

## Running the Server

### Option 1: Using the convenience script

```bash
python scripts/run_mcp_test_server.py
```

### Option 2: Using Python module

```bash
python -m app.modules.workflow.mcp.test_server
```

### Option 3: With custom port/host

```bash
python scripts/run_mcp_test_server.py 8001 0.0.0.0
```

The server will start on `http://localhost:8001` by default.

## Available Tools

1. **read_file**: Reads a file from storage
   - Parameters: `file_path` (string, required)

2. **write_file**: Writes content to a file
   - Parameters: `file_path` (string, required), `content` (string, required)

3. **list_files**: Lists all files in storage
   - Parameters: None

4. **delete_file**: Deletes a file from storage
   - Parameters: `file_path` (string, required)

5. **echo**: Echoes back a message
   - Parameters: `message` (string, required)

## API Endpoints

### HTTP-Based Protocol

#### Discover Tools
```bash
POST http://localhost:8001/tools/list
Content-Type: application/json
Authorization: Bearer <optional-api-key>

Response:
{
  "tools": [
    {
      "name": "read_file",
      "description": "Reads a file from the filesystem",
      "inputSchema": {...}
    },
    ...
  ]
}
```

#### Execute Tool
```bash
POST http://localhost:8001/tools/call
Content-Type: application/json
Authorization: Bearer <optional-api-key>

Request:
{
  "tool": "read_file",
  "toolArguments": {
    "file_path": "/path/to/file.txt"
  }
}

Response:
{
  "status": "success",
  "result": {
    "file_path": "/path/to/file.txt",
    "content": "file contents..."
  }
}
```

### JSON-RPC Protocol

#### Discover Tools
```bash
POST http://localhost:8001/jsonrpc
Content-Type: application/json

Request:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

Response:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [
    {
      "name": "read_file",
      "description": "Reads a file from the filesystem",
      "inputSchema": {...}
    },
    ...
  ]
}
```

#### Execute Tool
```bash
POST http://localhost:8001/jsonrpc
Content-Type: application/json

Request:
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "toolArguments": {
      "file_path": "/path/to/file.txt"
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": {
      "file_path": "/path/to/file.txt",
      "content": "file contents..."
    }
  }
}
```

## Testing with the MCP Node

1. Start the test server:
   ```bash
   python scripts/run_mcp_test_server.py
   ```

2. Use the server URL in your MCP node configuration:
   - Server URL: `http://localhost:8001`
   - API Key: (optional, leave empty for testing)

3. Discover tools using the API endpoint:
   ```bash
   curl -X POST http://localhost:8001/tools/list \
     -H "Content-Type: application/json"
   ```

4. Configure your MCP node with whitelisted tools and test execution.

## Example cURL Commands

### Discover Tools (HTTP)
```bash
curl -X POST http://localhost:8001/tools/list \
  -H "Content-Type: application/json"
```

### Write File (HTTP)
```bash
curl -X POST http://localhost:8001/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "write_file",
    "toolArguments": {
      "file_path": "/test/file.txt",
      "content": "Hello, World!"
    }
  }'
```

### Read File (HTTP)
```bash
curl -X POST http://localhost:8001/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "read_file",
    "toolArguments": {
      "file_path": "/test/file.txt"
    }
  }'
```

### List Files (JSON-RPC)
```bash
curl -X POST http://localhost:8001/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_files",
      "toolArguments": {}
    }
  }'
```

## Notes

- The server uses in-memory storage, so data is lost when the server restarts
- API key authentication is disabled for testing (all requests are accepted)
- The server supports both HTTP and JSON-RPC protocols simultaneously
- Error responses follow the respective protocol formats

