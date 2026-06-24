## Requirements Checklist

### Mandatory Requirements

| Required | Section | Module | Status | Notes |
| --- | --- | --- | --- | --- |
| Mandatory | (1) General | with frontend, backend, and db | ✅ | `make upd-build` then `make list`. Frontend is built in nginx volume|
| Mandatory | (2) General | use git with clear commit message | ✅ | check github commits |
| Mandatory | (3) General | docker & run with single command | ✅ | `make upd-build` |
| Mandatory | (4) General | must work in chrome. | ✅ | - |
| Mandatory | (5) General | no warning/errors (in the browser console) | ✅ | check the console (`make upd` has VITE dev server warnings) |
| Mandatory | (6) General | include accessible Privacy Policy & Terms of Service | ✅ | - |
| Mandatory | (7) General | multiple logins & simultaneous activity, concurrent actions handled properly, real-time updates broadcasted, no data corruption/race conditions. | ❗ | Open two Chrome profiles/incognito windows with different users, perform admin/user actions in parallel, watch dashboard live updates, then verify final DB/API state through UI and `make db-shell` or relevant API calls. |

### Technical Requirements

| Required | Section | Module | Status | Notes |
| --- | --- | --- | --- | --- |
| Mandatory | (1) Technical | responsive frontend across all devices | ✅ | check in chrome dev tools |
| Mandatory | (2) Technical | use a css framework/styling | ✅ | check `frontend/package.json` for `tailwindcss` and inspect `frontend/src/shared/styles` |
| Mandatory | (3) Technical | store credentials in local .env | ✅ | - |
| Mandatory | (4) Technical | database has clear schema & relations | ✅ | - |
| Mandatory | (5) Technical | have basic user management system (able to login & register securely) with email & passwd | ✅ | - |
| Mandatory | (6) Technical | all forms and user inputs must be properly validated in front- and backend | ❗ | Frontend: test invalid/empty inputs in UI and inspect `frontend/src/shared/lib/validation.ts`. Backend: send invalid payloads with `curl` or OpenAPI docs and confirm 4xx validation responses. |
| Mandatory | (7) Technical | https must be used eveywhere for the backend | ❗ | Browser-facing: open `https://localhost:8443`, check Network requests use HTTPS/WSS and `http://localhost:8080` redirects. Internal Docker traffic can remain service-to-service HTTP behind NGINX. |

### Major Modules

| Required | Section | Module | Status | Notes |
| --- | --- | --- | --- | --- |
| Module | (1) Major (Web) | a framework for both the frontend and backend: React frontend, FastAPI backend. | ✅ | search `import react` or `from fastapi` |
| Module | (2) Major (Web) | Real-time features using WebSockets: realtime update, handle connection/disconnection, efficient broadcasting | ❗ | Open dashboard as admin, inspect Network WS connection to `/api/ws/dashboard`, trigger a dashboard-changing action/import, and confirm connected clients refresh; disconnect/reconnect and repeat. |
| Module | (3) Major (Web) | User profiles, friends system, chat. | ⛔ | cancelled |
| Module | (4) Major (Web) | Documented/rate-limited API endpoints for artists, events, promoters, venues, recommendations, profile, etc. | ✅ | Open `http://localhost:8080/docs`, verify endpoint groups and schemas, then test key endpoints with the OpenAPI UI or `curl`; check rate-limit behavior where implemented. |
| Module | (5) Major (Data and Analytics) | Advanced analytics dashboard with data visualization: Charts, filters, date ranges, exports, real-time dashboard updates. | ✅ | log in as admin, open the dashboard, test |
| Module | (6) Major (AI) | Recommendation system using machine learning: Custom graph-based recommendation over artists, events, promoters, venues with explanation paths. | ✅ | - |
| Module | (7) Major (User management) | Advanced permissions system: view edit and delete users, roles management, different views and actions based on user role. | ✅ | log in as admin, open the dashboard, test |

### Minor Modules

| Required | Section | Module | Status | Notes |
| --- | --- | --- | --- | --- |
| Module | (1) Minor (Web) | Prisma/ORM usage for schema, migrations, and database queries. | ✅ | - |
| Module | (2) Minor (Web) | advanced search functionality across artists, events, promoters, venues with filters, sorting, pagination. | ✅ | use the search input field |
| Module | (3) Minor (Web) | Custom-made design system with reusable components, including a proper color palette, typography, and icons (minimum: 10 reusable components). | ✅ | Count reusable components in `frontend/src/shared/ui`, verify they are imported by pages/components, and check theme/color/typography files under `frontend/src/shared/styles`. |
| Module | (4) Minor (Data and Analytics) | Data export and import functionality: export analytics/recommendations/graph data as JSON/CSV and import curated event or artist datasets. | ✅ | log in as admin, open the dashboard, test OR test recommendation |
| Module | (5) Minor (Accessibility) | Support for additional browsers: Firefox/Safari/Edge, test and fix all features in each browser, document any browser-specific limitations, consistent UI/UX across all supported browsers. | ✅ | - |
