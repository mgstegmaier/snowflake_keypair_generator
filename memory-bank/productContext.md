# Product Context – Why this project exists

Snowflake access management often requires engineers to use the Snowflake UI or craft SQL statements manually. This is time-consuming, error-prone, and forces exposure of private keys on local machines.

Our app eliminates that friction by:
1. Abstracting complex SQL into one-click UI workflows (stored procedure calls under the hood).
2. Handling secure key-pair generation in-browser, never uploading private keys.
3. Offering OAuth-based authentication that aligns with enterprise SSO, avoiding password storage.
4. Providing visibility into existing databases/schemas/roles for faster role assignment.

Target users: DevOps and Data Engineers who maintain multiple Snowflake environments.

User experience goals:
• Minimalist dashboard with clear status indicators.  
• Zero-config start-up: clone repo, set env vars, `flask run`.  
• Real-time feedback (spinners, toasts) for long-running grants. 