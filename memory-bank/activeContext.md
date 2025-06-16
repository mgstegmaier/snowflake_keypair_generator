# Active Context – Current Focus

_Date:_ December 19, 2024

### Recent Changes
* **Phase 3 - Users Tab COMPLETED**: Full user management interface implemented
  - Backend: `/users`, `/users/<username>/unlock`, `/users/<username>/reset_password` routes
  - Frontend: Searchable users table with pagination, status filtering, action modals
  - UI: Bootstrap modals for unlock/reset password actions with validation
  - Integration: Uses existing `sp_unlock_user` and `sp_reset_password` stored procedures
* **Dynamic Application Width**: Changed from fixed 960px to responsive design
  - `min-width: 960px` with `width: max-content` and `max-width: 95vw`
  - Automatically accommodates wide tables and content
* **User Management UI Polish**:
  - Dark theme consistency (table-dark classes)
  - Compact dropdown actions with "Update User" button
  - Search functionality with proper button styling
  - Removed email column, optimized layout for screen space
* **Grant Permissions Flow**: Warehouse dropdown added and working
  - Defaults to `UPLAND_ENGINEERING_WH`, database defaults to `DEV_UPLAND_BRONZE_DB`
  - Fixed stored procedure authentication (Execute as Owner/DEFINER'S RIGHTS)
  - Enhanced error handling and logging

### Current Status - Implementation Plan Progress
✅ **Phase 0** - Infrastructure & Foundations  
✅ **Phase 1** - Session & Security Core (OAuth authentication)  
✅ **Phase 2** - Grant Permissions Tab (with warehouse dropdown)  
✅ **Phase 3** - Users Tab (JUST COMPLETED!)  
🔄 **Next**: Phase 4 - Roles Tab  
⏳ **Remaining**: Phase 5 - Public Key Management, Phase 6 - QA & Hardening

### In Progress / Next Steps
* **Phase 4 - Roles Tab**: Role listing with search and privilege details drawer
* Consider adding user creation functionality to Users tab
* Enhance error messages with more specific Snowflake error handling

### Open Questions
* Should we add user creation/deletion capabilities?
* Role hierarchy visualization in Roles tab?
* Integration with existing public key management script for Phase 5?

### Technical Notes
* Stored procedures now use DEFINER'S RIGHTS (Execute as Owner) with SECURITYADMIN
* All user management operations require proper warehouse context
* UI consistently uses dark theme with responsive Bootstrap components

### Recent Changes
* Added real Snowflake metadata queries in `snowflake_client.py`.
* Unit tests still green.
* Implemented PAT header enforcement.
* CI pipeline (Ruff + pytest) operational.
* Memory Bank maintained.
* Implemented dynamic dropdown load (databases, schemas, roles) with spinners and disabled Grant button until selections ready.
* Playwright e2e test skeleton (`tests/e2e/test_grant_flow.py`) added and skips if Playwright not installed.
* CI workflow rebuilt to install Playwright browsers and run e2e tests (Ubuntu, Python 3.11).
* Added PAT validation call and inactivity timeout enforcement in `require_pat`.
* New unit tests (`test_pat_security.py`) cover inactivity expiry.
* Removed PAT requirement: routes now protected by OAuth session only; front-end fetches directly without Authorization header.

### In Progress / Next Steps
None for now – major Phase-1 features complete.

### Open Questions
* Should we support multiple Snowflake accounts via UI selector?  
* Rate-limiting/graceful handling of Snowflake API errors? 