# Enhanced “Set / Rotate Key” Action (User Management Tab)

This document describes how to wire the new stored procedure `UPLAND_MAINTENANCE.SECURITY.sp_update_user_rsa_key` into the **Set / Rotate Key** flow in the web app.

---

## 1  Stored Procedure – Full Definition *(EXECUTE AS OWNER)*

```sql
USE ROLE SECURITYADMIN;
USE DATABASE UPLAND_MAINTENANCE;
USE SCHEMA SECURITY;

/*
  sp_update_user_rsa_key
  ----------------------
  • Sets RSA_PUBLIC_KEY (only) for a user
  • Optional: PASSWORD = NULL when p_unset_password = TRUE
  • Optional: change TYPE → PERSON | SERVICE | LEGACY_SERVICE | NULL
*/
CREATE OR REPLACE PROCEDURE sp_update_user_rsa_key (
        p_username          STRING,             -- required
        p_rsa_public_key    STRING,             -- required, headers removed
        p_unset_password    BOOLEAN   DEFAULT FALSE,
        p_new_type          STRING    DEFAULT NULL
)
RETURNS STRING
LANGUAGE JAVASCRIPT
EXECUTE AS OWNER
AS
$$
  // Validate TYPE if provided
  var newType = (P_NEW_TYPE ? P_NEW_TYPE.trim().toUpperCase() : null);
  var allowed = ['PERSON','SERVICE','LEGACY_SERVICE','NULL'];
  if (newType && allowed.indexOf(newType) === -1) {
      throw "Invalid TYPE. Allowed: PERSON, SERVICE, LEGACY_SERVICE, NULL";
  }

  // Build ALTER USER SET list
  var setList = [];
  setList.push("RSA_PUBLIC_KEY = '" + P_RSA_PUBLIC_KEY.replace(/'/g,"''") + "'");
  if (P_UNSET_PASSWORD) {
      setList.push("PASSWORD = NULL");
  }
  if (newType) {
      setList.push("TYPE = " + newType);
  }

  var sqlCmd = 'ALTER USER "' + P_USERNAME + '" SET ' + setList.join(', ');
  snowflake.execute({sqlText: sqlCmd});
  return 'User ' + P_USERNAME + ' updated successfully.';
$$;

-- Grant USAGE to SYSADMIN
GRANT USAGE ON PROCEDURE UPLAND_MAINTENANCE.SECURITY.sp_update_user_rsa_key(
         STRING, STRING, BOOLEAN, STRING
      )
TO ROLE SYSADMIN;
```

*Owned by **``**; **``** already has USAGE privilege.*

---

## 2  UI / UX Changes

| UI Element                                                | Purpose                                                                                                                                     | Proc Parameter                                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Passphrase** (existing)                                 | Generates new RSA key pair and returns public key                                                                                           | `p_rsa_public_key`                                                         |
| **Check‑box** – “Unset password (disable password login)” | `TRUE` when checked                                                                                                                         | `p_unset_password`                                                         |
| **Check‑box** – “Change user type”                        | When **checked** the dropdown below is displayed; when **unchecked** the dropdown is hidden *and no value is passed to* `p_new_type` (NULL) | *(controls dropdown visibility)*                                           |
| **Dropdown** – “User type”                                | Visible **only** if the above box is checked. Values: `PERSON`, `SERVICE`, `LEGACY_SERVICE`, `NULL / Unchanged`                             | `p_new_type` (NULL if checkbox is unchecked **or** dropdown = "Unchanged") |

\--------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------- | | **Passphrase** (existing)                                 | Generates new RSA key pair and returns public key                  | `p_rsa_public_key`               | | **Check‑box** – “Unset password (disable password login)” | `TRUE` when checked                                                | `p_unset_password`               | | **Dropdown** – “Change user type”                         | Options: `PERSON`, `SERVICE`, `LEGACY_SERVICE`, `NULL / Unchanged` | `p_new_type` (NULL if unchanged) |

---

## 3  End‑to‑End Flow

1. Admin clicks **Set / Rotate Key** on a user row.
2. Modal opens with the three controls above.
3. On **Submit**:
   1. Front‑end generates the key pair, strips PEM headers, prepares payload.
   2. Backend executes the stored procedure:
      ```sql
      CALL UPLAND_MAINTENANCE.SECURITY.sp_update_user_rsa_key(
          :username,
          :clean_public_key,
          :unset_password_boolean,
          :new_type_string  -- NULL if unchanged
      );
      ```
4. **Result Handling**
   - Success → output completed actions in the modal's results message box similar to how it is currently behaving
   - Error   → surface Snowflake error in the results message box.
5. If session policy is “clear token after action,” wipe OAuth token once the call completes.

---

## 4  Edge Cases & Validation

- **TYPE** values allowed: `PERSON`, `SERVICE`, `LEGACY_SERVICE`, `NULL` (validated client‑side and by proc).
- If *Unset password* is checked, display warning that password login will be disabled.
- Show user‑friendly error if RSA key format is invalid.

---

## 5  Developer Checklist

*(All steps must be completed before marking the feature as DONE)*

- **Modal UI:** add check-box and dropdown with values above.
- **Front-end:** strip PEM headers, build payload, call backend.
- **Backend:** call stored procedure with 4 params, return message to UI.
- **Validation:** enforce allowed types, handle checkbox → boolean.
- **Session handling:** if “clear after action,” wipe OAuth token post-call.

