# System Patterns – Architecture & Design Decisions

```mermaid
flowchart TD
    Browser -->|OAuth 2.0| SnowflakeIdP[Snowflake OAuth]
    Browser -->|REST API| FlaskAPI[Flask Backend]
    FlaskAPI -->|Session Auth| SnowflakeConn[Snowflake Connector]
    FlaskAPI -->|DEFINER'S RIGHTS| StoredProcs[Security Stored Procs]
    
    subgraph "User Management"
        FlaskAPI --> UserRoutes[/users, /users/unlock, /users/reset]
        UserRoutes --> StoredProcs
    end
    
    subgraph "Permission Management"
        FlaskAPI --> PermRoutes[/grant_permissions]
        PermRoutes --> StoredProcs
    end
```

## Core Architectural Patterns

• **Layered separation**  
  – Front-end: Bootstrap 5 + vanilla JS in `templates/index.html`  
  – Backend: Flask routes in `app.py` with OAuth session management  
  – Data layer: `snowflake_client.py` thin wrapper with connection pooling

• **Responsive UI Design**  
  – Dynamic width: `min-width: 960px` with `width: max-content`  
  – Dark theme consistency across all components  
  – Bootstrap modals for complex interactions (user management)  
  – Professional table layouts with pagination and search

• **Token lifecycle & Security**  
  – OAuth 2.0 with Snowflake as identity provider  
  – Session-based authentication (no PAT requirements)  
  – Stored procedures use DEFINER'S RIGHTS (Execute as Owner) pattern  
  – Private keys never leave browser environment

• **API Design Patterns**  
  – RESTful routes: `/users`, `/users/<id>/unlock`, `/users/<id>/reset_password`  
  – Consistent JSON responses with `success`, `message`, `data` structure  
  – Comprehensive error handling with user-friendly messages  
  – Authentication middleware with `@require_oauth` decorator

• **Data Management**  
  – Metadata caching: databases, schemas, roles, warehouses loaded on-demand  
  – Pagination for large datasets (20 items per page)  
  – Real-time search and filtering client-side  
  – Default values: `UPLAND_ENGINEERING_WH`, `DEV_UPLAND_BRONZE_DB`

• **Testing strategy**  
  – Unit tests with pytest + Flask test client  
  – Monkeypatch pattern for mocking Snowflake connections  
  – Playwright e2e framework for integration testing  
  – CI/CD with GitHub Actions

• **UI Component Patterns**  
  – Searchable tables with status badges  
  – Action dropdowns with validation  
  – Toast notifications for user feedback  
  – Loading states with Bootstrap spinners  
  – Form validation with real-time feedback

• **Security Architecture**  
  – `require_oauth` decorator for route protection  
  – Warehouse context setting for stored procedure execution  
  – XSS protection through Jinja2 template escaping  
  – CSRF protection via Flask session management

• **Error Handling Patterns**  
  – Graceful degradation for API failures  
  – User-friendly error messages  
  – Detailed logging for debugging  
  – Fallback UI states for empty data sets
