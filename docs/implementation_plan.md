# Implementation Roadmap – Snowflake Admin App

_Last updated: {{DATE}}_

---

## Overview
This roadmap breaks development into six phases, each ending with a demo-ready deliverable.  Security considerations (PAT handling, inactivity timer, zero long-term storage) apply throughout.

| Phase | Focus | Duration* | Key Deliverables |
|-------|-------|-----------|------------------|
| 0 | Infrastructure & foundations | 1 day | Repo restructure, utilities, tests | 
| 1 | Session & security core | 2-3 days | PAT prompt, inactivity timer, sidebar toggle | 
| 2 | Grant Permissions tab | 2 days | Guided form calling grant/revoke procs | 
| 3 | Users tab | 3 days | User list, search, unlock/reset actions | 
| 4 | Roles tab | 2 days | Role list, details drawer | 
| 5 | Public Key Management | 1 day | Key cleanup & update flow | 
| 6 | QA / Docs | 1 day | Cypress tests, Dockerfile, README |

_*Durations are rough dev-days._

---

## Phase 0 – Infrastructure & Foundations
1. **Repo structure**  
   `backend/` (Flask app, utils)  
   `frontend/` (templates, static)  
   `docs/` (specs like this file)
2. **Utilities**  
   `snowflake_client.py` – thin wrapper around Snowflake connector and stored-proc execution.  
   `security.py` – inactivity timer helpers, PAT validation.
3. **Env & tests**  
   `.env` for non-secret defaults.  
   Pytest unit tests for the two utility modules.

## Phase 1 – Session & Security Core
* Sidebar session-security toggle (default ON)
* Reusable PAT prompt modal (Bootstrap)
* Inactivity timer (15 min)
* Flask middleware for PAT header

## Phase 2 – Grant Permissions Tab
* Database → Schema → Role dropdowns (dynamic)
* Permission-type radios (RO / RW / DB-wide)
* `/grant_permissions` backend route invoking stored procs

## Phase 3 – Users Tab
* Searchable/filtered users table (Bootstrap)
* Unlock & reset-password quick actions (modals)
* Pagination if >100 users

## Phase 4 – Roles Tab
* Roles table with search
* Off-canvas drawer for users & privileges

## Phase 5 – Public Key Management Tab
* Username select + public-key cleanup on paste/upload
* `/set_public_key` backend route

## Phase 6 – QA & Hardening
* Cypress end-to-end tests* Dockerfile/Compose

---

## Security Principles Recap
1. PAT only in memory or `sessionStorage` (never disk).  
2. Inactivity timer clears PAT after 15 min.  
3. Sidebar toggle sets policy (keep vs clear after each sensitive action).  
4. Backend requires `Authorization: Bearer <PAT>` for admin routes.

---

_The plan can evolve; update this file as scope or priorities shift._ 