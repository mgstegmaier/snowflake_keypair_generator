# Project Brief – Snowflake Admin App

## Vision
A secure, browser-based administration dashboard that streamlines Snowflake key-pair creation, processing, and permission management for engineering teams.  

## Core Requirements
1. Provide a simple UI for:
   • Generating RSA key pairs for users.  
   • Processing existing private keys (remove line breaks, Base64 encode).  
   • Visualising and managing database objects (databases, schemas, roles).  
   • Granting read, read-write, or DB-wide permissions via stored procedures.
2. Authenticate users with Snowflake OAuth (client-secret / HS256) and persist session via refresh tokens.
3. Enforce Personal Access Token (PAT) header for protected API routes.
4. Communicate with Snowflake through a thin Python wrapper (`backend/snowflake_client.py`).  
5. Maintain CI that lint-checks with Ruff and runs pytest on every PR.

## Success Criteria
• All key workflows accessible from the dashboard without manual SQL.  
• OAuth login indicator accurate and no console errors.  
• Unit and e2e tests green in CI.  
 