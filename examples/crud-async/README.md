# Async CRUD Example

An async CRUD application using pico-sqlalchemy with the repository pattern and SQLite.

## Requirements

- Python 3.11+

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m app.main
```

This will:
1. Create an in-memory SQLite database
2. Create the `users` table
3. Perform CRUD operations
4. Print results to the console
