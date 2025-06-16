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

## UI Color Palette & Design System

### Brand Color Palette
| Role | Hex Code | CSS Variable | Usage |
|------|----------|--------------|-------|
| Brand/Main | `#c36c2d` | `--brand-main` | Primary brand color, headers, key elements |
| Light Shade | `#faf7f2` | `--light-shade` | Primary text color, light backgrounds |
| Light Accent | `#c59f6b` | `--light-accent` | Hover states, secondary highlights |
| Dark Shade | `#a26d58` | `--dark-shade` | Muted elements, borders |
| Dark Accent | `#2f2e3c` | `--dark-accent` | Background elements, cards |

### Semantic Color Palette
| Color Name | Hex Code | CSS Variable | Bootstrap Context | Usage |
|------------|----------|--------------|-------------------|-------|
| Tuscany | `#c56c30` | `--tuscany` | Primary | Main action buttons, primary CTAs |
| Charade | `#252430` | `--charade` | Info | Background, informational elements |
| Asparagus | `#709b46` | `--asparagus` | Success | Success states, positive indicators |
| Golden Bell | `#ee8b0e` | `--golden-bell` | Warning | Warning states, attention needed |
| Pomegranate | `#f44336` | `--pomegranate` | Danger | Error states, destructive actions |

### Application-Specific Colors
| Element | Hex Code | CSS Variable | Usage |
|---------|----------|--------------|-------|
| Dark Background | `var(--charade)` | `--dark-bg` | Sidebar background |
| Secondary Background | `#2e2c38` | `--secondary-bg` | Main app background |
| Darker Background | `#1a1820` | `--darker-bg` | Form inputs, deeper elements |
| Card Background | `#3a3848` | `--card-bg` | Card/modal backgrounds |
| Text Color | `var(--light-shade)` | `--text-color` | Primary text |
| Border Color | `#4a4858` | `--border-color` | Element borders |
| Muted Text | `#b8b5a8` | `--muted-text` | Secondary text, labels |

### Security Indicator Colors
- **Success/Enabled**: `var(--asparagus)` with white text
- **Disabled/Not Set**: `#6c757d` (Bootstrap secondary) with dark text
- **Active Status**: `var(--asparagus)` 
- **Locked Status**: `var(--pomegranate)`
- **Warning Status**: `var(--golden-bell)`

### Implementation Notes
- All colors defined as CSS custom properties in `:root`
- Semantic colors align with Bootstrap 5.3 contextual classes
- Dark theme optimized for professional administrative interface
- Consistent hover states use `--light-accent` for interactive elements
- Focus states use 25% opacity of primary brand color for accessibility
- Bootstrap badge classes overridden with custom semantic colors
