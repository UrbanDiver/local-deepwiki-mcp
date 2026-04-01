# Module: sample_repo

## Module Purpose

This module represents a sample repository structure used for testing and demonstration purposes. It contains core application components including data models, a parser for processing user data, and supporting utilities. The module also includes test fixtures and conftest configurations that define shared testing resources and test cases.

## Key Classes and Functions

### User
A registered user of the system with attributes:
- `user_id`: Unique identifier for the user
- `name`: Full display name
- `email`: Contact email address
- `created_at`: Timestamp when the user was created

The class includes a `display_label()` method that returns a human-readable label in the format 'Name <email>'.

### Order
A purchase order placed by a user with attributes:
- `order_id`: Unique identifier for the order
- `user_id`: The ID of the user who placed the order
- `items`: List of item names in the order (default empty list)
- `total`: Total price in dollars (default 0.0)

The class includes an `item_count()` method that returns the number of items in the order.

### DataParser
A parser class responsible for converting dictionary data into User objects. The `parse()` method:
- Takes a dictionary containing user data
- Returns a User instance for valid input
- Raises KeyError for missing required fields

### ExternalClient
A client for communicating with an external data service that manages connection lifecycle and provides typed data retrieval.

### format_name
A utility function (defined in src/utils.py) for formatting names.

### sample_user
A pytest fixture function that creates a User instance for testing purposes.

## How Components Interact

The module demonstrates a typical application structure where:
1. `User` and `Order` data models define the core domain objects
2. `DataParser` processes input data into these model instances
3. `ExternalClient` provides integration with external services
4. Test files (`test_models.py`, `test_parser.py`) validate functionality through unit tests
5. `conftest.py` defines shared fixtures used across multiple test files

The `User` class depends on the `display_label()` method to format user information for display, while `DataParser` creates `User` instances from dictionary data.

## Usage Examples

### Creating a User instance:
```python
from src.models import User
from datetime import datetime

user = User(
    user_id=1,
    name="Alice",
    email="alice@example.com"
)
print(user.display_label())  # Output: "Alice <alice@example.com>"
```

### Using DataParser to parse data:
```python
from src.parser import DataParser
from src.models import User

parser = DataParser()
user_data = {"user_id": 1, "name": "Bob", "email": "bob@example.com"}
user = parser.parse(user_data)
assert isinstance(user, User)
```

### Using ExternalClient:
```python
from lib.external import ExternalClient

client = ExternalClient(base_url="https://api.example.com")
client.connect()
data = client.fetch("/users/123")
```

## Dependencies

This module depends on the following components based on imports shown:

- `src.models`: Provides User and Order dataclasses
- `src.parser`: Provides DataParser class
- `src.utils`: Provides format_name utility function
- `lib.external`: Provides ExternalClient class
- `pytest`: For testing framework support
- `unittest.mock`: For mocking dependencies in tests
- Standard library modules: dataclasses, datetime, hashlib, json, pathlib, re, typing

The module also imports from the `src` package namespace which contains:
- `src.models`
- `src.parser` 
- `src.utils`
- `src.sub.processor` (indirectly through src/__init__.py)