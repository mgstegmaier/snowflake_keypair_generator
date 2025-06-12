# Snowflake Admin App: User Stories & Developer Instructions

*The content below mirrors the latest markdown provided by the product owner.*

---

## General Principles (For All Tabs)

- **Security:**
  - All sensitive information, including the Snowflake Personal Access Token (PAT), must only exist in browser memory or `sessionStorage`—never persist to disk or localStorage.
  - Inactivity timer: If the user is inactive for 15 minutes, clear the PAT and require re-entry.
  - **Session security toggle:** A single toggle at the bottom of the sidebar allows the user to choose whether the PAT is kept in memory for the session, or cleared after each sensitive action. This setting must reset with each new session.
  - All sensitive actions must prompt for a PAT if not present in memory/session, and handle session expiry gracefully.

---

## 1. Grant Permissions Tab

**User Story:**\
As an admin, I want to grant read-only, read/write, or database-wide permissions to a role for a given database and schema using stored procedures, with guided dropdowns to select database, schema, and role.

**Workflow:**

- On tab load, fetch and display a dropdown of all databases in the Snowflake account.
- When a database is selected, fetch and display a dropdown of all schemas in that database.
- Separately, fetch and display a dropdown of all roles.
- User selects a database, then a schema (or leaves schema blank for DB-wide), then a role.
- User selects permission type (read-only, read/write, or DB-wide).
- On submit, invoke the appropriate stored procedure with the chosen parameters.
- After submission, display a clear success or error message.
- If session security is set to clear PAT after each action, remove PAT from memory/session after successful grant.

**Edge Cases:**

- Show loading indicators while fetching picklists.
- Handle empty or missing options gracefully.
- Show validation errors if any required selection is missing.

---

## 2. Users Tab

**User Story:**\
As an admin, I want to see a list of all users in the Snowflake account, search or filter by name, status, or role, and perform quick actions like unlocking or resetting a password.

**Workflow:**

- On tab load, fetch and display a searchable, filterable table of all users, including columns for name, status (locked/unlocked), roles, and last login time.
- Provide inline quick actions for each user:
  - Unlock account
  - Reset password
  - View user details (optional)
- On action, confirm the user's intent (e.g., modal or dialog) before submitting the change.
- After action, refresh the relevant user's row and display a success or error message.
- If session security is set to clear PAT after each action, clear the PAT after the operation.

**Edge Cases:**

- Handle users with no roles, or multiple roles, and display accordingly.
- Gracefully handle API errors and provide clear error messages to the user.

---

## 3. Roles Tab

**User Story:**\
As an admin, I want to see a list of all roles, search for a specific role, and view detailed information about each role, including which users have the role and what permissions/privileges it holds.

**Workflow:**

- On tab load, fetch and display a searchable list/table of all roles.
- Clicking a role opens a details view or drawer:
  - List of users assigned to this role.
  - List of privileges and objects this role has access to.
- Allow user to search roles by name.
- All actions requiring PAT must check session security settings and clear the PAT after each sensitive action if the setting is off.

**Edge Cases:**

- Gracefully handle roles with no assigned users or no privileges.
- Handle large role lists efficiently (pagination or virtual scroll if needed).

---

## 4. Public Key Management Tab

**User Story:**\
As an admin, I want to set or update the RSA public key for a given user, and I want the app to automatically clean up pasted keys by removing any PEM headers, footers, and whitespace before submitting to Snowflake.

**Workflow:**

- Provide a form to select or enter a username and paste or upload a public key.
- When a key is pasted or uploaded, automatically strip out any `-----BEGIN PUBLIC KEY-----`, `-----END PUBLIC KEY-----`, and all whitespace or newlines, leaving only the raw base64-encoded key content.
- On submit, update the user's public key in Snowflake.
- Display a clear success or error message after the operation.
- If session security is set to clear PAT after each action, clear it after the key is set.

**Edge Cases:**

- If the key is not in PEM format or is otherwise invalid, display a user-friendly error.
- Allow repeated attempts without requiring a full page reload.

---

## 5. Session & Security Handling (Cross-Feature)

- **PAT Handling:**
  - Check for a valid PAT in session/memory before any sensitive operation.
  - If not present, prompt user to enter their PAT.
  - If session security toggle is OFF, clear PAT from memory/session immediately after each sensitive operation.
  - If session security toggle is ON, keep PAT until inactivity timer (15 minutes), tab close, or manual logout/clear.
- **Inactivity Timer:**
  - Any user activity (mouse, keyboard, touch) resets the inactivity timer.
  - If 15 minutes pass with no interaction, clear PAT and session settings, and require re-authentication.

---

# Appendix: Stored Procedures

## Permissions Management Stored Procedures

*(Full definitions as provided in the spec – truncated here for brevity)*

- `UPLAND_MAINTENANCE.SECURITY.sp_grant_read_perms(VARCHAR, VARCHAR, VARCHAR)`
- `UPLAND_MAINTENANCE.SECURITY.sp_revoke_read_perms(VARCHAR, VARCHAR, VARCHAR)`
- `UPLAND_MAINTENANCE.SECURITY.sp_grant_readwrite_perms(STRING, STRING, STRING, BOOLEAN)`
- `UPLAND_MAINTENANCE.SECURITY.sp_revoke_readwrite_perms(STRING, STRING, STRING, BOOLEAN)`

## User Management Stored Procedures

- `UPLAND_MAINTENANCE.SECURITY.sp_unlock_user(STRING)`
- `UPLAND_MAINTENANCE.SECURITY.sp_reset_password(STRING, STRING)`
- `UPLAND_MAINTENANCE.SECURITY.sp_set_public_key(STRING, STRING)`

---

# Summary: What Developers Should Deliver per Tab

- **Grant Permissions:** Guided form, picklists, stored proc integration, PAT/session handling.
- **Users:** List, search/filter, inline actions (unlock, reset password), PAT/session handling.
- **Roles:** List, search, detail view (users, privileges), PAT/session handling.
- **Public Key Management:** User/key form, silent key cleaning, update key in Snowflake, PAT/session handling.
- **Session security toggle:** Single toggle at bottom of sidebar, affecting all sensitive actions in current session.

**All features must strictly adhere to session-only security and zero long-term retention of sensitive data.** 