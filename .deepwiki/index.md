# Local DeepWiki MCP

A local implementation of the DeepWiki Multi-Client Protocol (MCP) for building and managing local knowledge bases with multi-client support and semantic search capabilities.

## Description

Local DeepWiki MCP provides a self-hosted solution for creating and managing local knowledge bases with support for multiple client connections. It implements the DeepWiki protocol to enable semantic search, knowledge graph construction, and multi-client collaboration in a local environment.

## Key Features

- **Multi-Client Support**: Handle multiple concurrent client connections with isolated knowledge contexts
- **Semantic Search**: Advanced search capabilities with vector embeddings and semantic similarity
- **Knowledge Graph Construction**: Build and maintain interconnected knowledge structures
- **Local Storage**: All data stored locally without external dependencies
- **Protocol Compliance**: Implements the DeepWiki Multi-Client Protocol for interoperability
- **Modular Architecture**: Clean separation of concerns for easy extension and maintenance

## Technology Stack

- **Core Language**: Python 3.8+
- **Web Framework**: FastAPI for REST API endpoints
- **Database**: SQLite with SQLAlchemy ORM
- **Vector Storage**: ChromaDB for vector embeddings
- **Search**: Semantic search with embedding models
- **Authentication**: JWT-based authentication system
- **Documentation**: Markdown-based documentation generation

## Directory Structure

```
local-deepwiki-mcp/
├── app/                    # Main application modules
│   ├── core/             # Core functionality and business logic
│   ├── models/           # Data models and database schemas
│   ├── services/         # Service layer for business operations
│   ├── api/              # API endpoints and routing
│   └── utils/            # Utility functions and helpers
├── data/                 # Local data storage and configuration
├── tests/                # Test suite
├── docs/                 # Documentation files
├── config/               # Configuration files
├── migrations/           # Database migration scripts
└── requirements.txt      # Python dependencies
```

## Quick Start Guide

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/local-deepwiki-mcp.git
cd local-deepwiki-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Start the application
python main.py

# Or run with specific configuration
python main.py --config config/local.json
```

### API Endpoints

The API is available at `http://localhost:8000` with the following endpoints:

- `POST /clients` - Register new client
- `POST /knowledge` - Add knowledge to knowledge base
- `POST /search` - Perform semantic search
- `GET /status` - Get system status

### Configuration

Create a configuration file in `config/local.json`:

```json
{
    "database": {
        "path": "data/local.db"
    },
    "embedding": {
        "model": "all-MiniLM-L6-v2"
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000
    }
}
```

### Testing

Run the test suite:

```bash
python -m pytest tests/
```

For detailed documentation and usage examples, refer to the documentation in the docs/ directory.