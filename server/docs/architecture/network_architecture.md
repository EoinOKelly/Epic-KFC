# Network Architecture

## Step 1 Scope

This document records the intended network shape for the backend setup. It is
planning documentation only at this stage; no authentication, message routes,
database tables, migrations, or blockchain integration are implemented yet.

## Intended Components

- Client application: sends HTTPS requests to the FastAPI backend.
- FastAPI backend: validates API requests, enforces authentication and
  authorisation in later steps, and communicates with PostgreSQL.
- PostgreSQL database: stores user records, encrypted message ciphertext, and
  message metadata in later steps.
- Deployment edge: terminates TLS in production or forwards traffic to the
  FastAPI application over a trusted internal network.

## Trust Boundaries

- Client-to-backend traffic must use HTTPS in deployed environments.
- Backend-to-database traffic should stay on a private network or equivalent
  restricted environment.
- The backend must never store plaintext message contents because the messaging
  design assumes end-to-end encryption.
- Logs must avoid passwords, tokens, private keys, plaintext messages, and
  unnecessary ciphertext.

## Future Planning Notes

- Authentication and authorisation will be added in later steps.
- SQLAlchemy will use the async ORM with `asyncpg`.
- Blockchain integration is out of scope for Step 1 and should remain a future
  planning topic only.
