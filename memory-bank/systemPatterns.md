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
    
    subgraph "System Monitoring"
        FlaskAPI --> LogsRoute[/logs]
        LogsRoute --> LogProcessor[Log Processing & Filtering]
        Browser --> AutoRefresh[Auto-refresh Management]
    end
```

## Core Architectural Patterns

• **Layered separation**  
  – Front-end: Bootstrap 5 + vanilla JS in `templates/index.html`  
  – Backend: Flask routes in `app.py` with OAuth session management  
  – Data layer: `snowflake_client.py` thin wrapper with connection pooling
  – Monitoring layer: Real-time log processing with filtering and auto-refresh

• **Responsive UI Design**  
  – Dynamic width: `min-width: 960px` with `width: max-content`  
  – Dark theme consistency across all components including monitoring interfaces
  – Bootstrap modals for complex interactions (user management, log details)  
  – Professional table layouts with pagination, search, and real-time monitoring

• **Real-time Monitoring Architecture**
  – Server Logs tab with auto-refresh capabilities (5-second intervals)
  – Multi-dimensional filtering: log level, search terms, line count control
  – Interactive log display with color-coded levels and expandable details
  – Resource-efficient management: auto-refresh starts/stops based on tab visibility

• **Token lifecycle & Security**  
  – OAuth 2.0 with Snowflake as identity provider  
  – Session-based authentication (no PAT requirements)  
  – Stored procedures use DEFINER'S RIGHTS (Execute as Owner) pattern  
  – Private keys never leave browser environment
  – Secure log access with OAuth protection for monitoring endpoints

• **API Design Patterns**  
  – RESTful routes: `/users`, `/users/<id>/unlock`, `/users/<id>/reset_password`, `/logs`  
  – Consistent JSON responses with `success`, `message`, `data` structure  
  – Comprehensive error handling with user-friendly messages  
  – Authentication middleware with `@require_oauth` decorator
  – Filtering support for monitoring endpoints with query parameters

• **Data Management**  
  – Metadata caching: databases, schemas, roles, warehouses loaded on-demand  
  – Pagination for large datasets (20 items per page)  
  – Real-time search and filtering client-side  
  – Default values: `UPLAND_ENGINEERING_WH`, `DEV_UPLAND_BRONZE_DB`
  – Log data processing with efficient filtering and chronological ordering

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
  – Interactive log display with color-coded entries and hover effects

• **Security Architecture**  
  – `require_oauth` decorator for route protection  
  – Warehouse context setting for stored procedure execution  
  – XSS protection through Jinja2 template escaping  
  – CSRF protection via Flask session management
  – Secure log access with authentication requirements

• **Error Handling Patterns**  
  – Graceful degradation for API failures  
  – User-friendly error messages  
  – Detailed logging for debugging  
  – Fallback UI states for empty data sets
  – Comprehensive error management in monitoring endpoints

• **Performance Optimization Patterns**
  – Client-side filtering and sorting for immediate responsiveness
  – Debounced search inputs to prevent excessive API calls
  – Intelligent auto-refresh management for resource efficiency
  – Cached data structures for instant user detail access
  – Optimized database queries with single-view architecture

## Monitoring & Debugging Architecture

### Real-time Log Monitoring System
| Component | Implementation | Purpose |
|-----------|----------------|---------|
| Server Logs Tab | Bootstrap tab with terminal-style interface | Professional log viewing experience |
| Auto-refresh Management | 5-second intervals with tab visibility detection | Resource-efficient real-time monitoring |
| Multi-level Filtering | Log level, search terms, line count controls | Precise log analysis capabilities |
| Interactive Display | Color-coded entries with click-to-expand details | Enhanced debugging experience |

### Backend Log Processing
```python
# Log endpoint pattern
@app.route('/logs')
@require_oauth
def get_server_logs():
    # Multi-dimensional filtering support
    lines = request.args.get('lines', '100', type=int)
    level_filter = request.args.get('level', '')
    search_term = request.args.get('search', '')
    
    # Structured response with metadata
    return jsonify({
        'success': True,
        'logs': processed_logs,
        'total_lines': len(logs),
        'filters': filter_metadata,
        'timestamp': current_timestamp
    })
```

### Frontend Monitoring Patterns
- **Tab Management**: Auto-load logs when tab shown, cleanup when hidden
- **Event Handling**: Comprehensive event management for filters, search, navigation
- **Resource Management**: Proper cleanup of intervals and event listeners
- **User Experience**: Smooth scrolling, hover effects, and interactive feedback

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

### Log Level Color Coding
| Log Level | Hex Code | Usage |
|-----------|----------|-------|
| DEBUG | `#6c757d` | Debug information, detailed tracing |
| INFO | `#17a2b8` | General information, normal operations |
| WARNING | `#ffc107` | Warning conditions, attention needed |
| ERROR | `#dc3545` | Error conditions, failed operations |
| CRITICAL | `#721c24` | Critical errors, system failures |

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
- Log level colors provide clear visual distinction for monitoring interface

### Monitoring Interface Design Patterns
- **Terminal Aesthetics**: Monospace font with black background for authentic log viewing
- **Interactive Elements**: Hover effects and click-to-expand functionality
- **Professional Layout**: Card-based design with header, body, and footer sections
- **Status Indicators**: Color-coded log levels with consistent visual hierarchy
- **Resource Efficiency**: Smart auto-refresh management with user control
