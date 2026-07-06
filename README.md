# Cashflow Web Application Structure

## Overview
This repository contains a personal finance tracking application built with Python and Flask.

## Directory Structure

```text
app/
├── __init__.py                # Flask app factory
├── routes/
│   ├── auth.py               # Authentication routes
│   ├── pages.py              # Main page routes
│   ├── transactions.py       # Transaction routes
│   ├── debts.py              # Debt routes
│   └── masterdata.py         # Summary & master data routes
├── services/
│   ├── account_service.py    # Account management business logic
│   ├── debt_service.py       # Debt management business logic
│   └── transaction_service.py # Transaction management business logic
├── db.py                     # Database helper functions
├── models.py                 # User authentication models
└── 
├── static/
│   ├── js/
│   │   ├── app.js
│   │   ├── settings.js
│   │   └── transactions.js
│   └── css/                  # (if any CSS files)
└── templates/
    ├── auth/                # Login & registration
    │   └── login.html
    ├── dashboard/            # Dashboard page
    │   └── dashboard.html
    ├── layout/              # Shared layout components
    │   └── _sidebar.html
    ├── tools/               # Tools section (previously settings)
    │   └── settings.html
    └── transactions/        # Transactions page
        └── transactions.html
```

## Key Features

### Authentication
- User registration
- User login/logout
- Secure password hashing

### Dashboard & Pages
- Main overview with account statistics
- Transactions management
- Tools section (account management)

### Financial Tracking
- **Transactions**: Create, read, update, delete operations
- **Accounts**: Create, read, update, delete with balance tracking
- **Categories**: Income/expense categories management
- **Debts**: Debt tracking with payment management

### API Endpoints
All API routes are organized under blueprints:
- `auth_bp`: `/api/user` (DELETE)
- `transactions_bp`: `/api/transactions` (GET, POST, DELETE)
- `debts_bp`: `/api/debts` (GET, POST), `/api/debts/<id>/pay` (POST)
- `masterdata_bp`: `/api/summary`, `/api/categories`, `/api/accounts/count`, etc.

## Tech Stack

- **Framework**: Flask
- **Database**: SQLite (per-user databases)
- **Template Engine**: Flask's built-in Jinja2
- **Security**: Password hashing, session management, HTTPS headers
- **Architecture**: Blueprint-based, Service layer for business logic separation

## API Design Notes

### Pagination
All list endpoints implement cursor-based pagination via query parameters:
- `?cursor=<opaque_token>`
- Returns next cursor for next page
- Optimized for mobile and slow networks

### Error Handling
Consistent error format:
```json
{"error": "Human readable error message"}
```

### Rate Limiting
Sliding window rate limiting implemented for API protection.

## Deployment

```bash
# Build and run with Docker
./build.sh

# Or using docker-compose
docker compose up -d
```

## Contribution

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
