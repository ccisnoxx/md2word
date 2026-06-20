# Frontend API Contract Guidelines

## Scope

These rules apply to frontend API wrappers under `frontend/src/api/` and page-level request builders that pass query parameters to the FastAPI backend.

## Optional Query Parameters

Omit optional query parameters when the UI value is empty. Do not send empty strings for enum filters such as role, status, stage, or sort fields.

FastAPI/Pydantic validates query enum values before route code runs. Sending `status=` or `role=` to an endpoint typed as `"active" | "disabled"` or `"admin" | "operator"` returns `422 validation_error`, even though the user's intent is "all statuses" or "all roles".

```typescript
// Wrong: sends role="" and status="" after clearable selects are reset.
api.list({
  role: filters.role,
  status: filters.status,
});

// Correct: omit unselected enum filters.
api.list({
  role: filters.role || undefined,
  status: filters.status || undefined,
});
```

When a wrapper owns the endpoint contract, prefer a small parameter builder that trims keyword fields and returns only meaningful keys:

```typescript
function buildListParams(params: ListQuery): ListQuery {
  const query: ListQuery = {};
  const keyword = params.keyword?.trim();
  if (keyword) {
    query.keyword = keyword;
  }
  if (params.status) {
    query.status = params.status;
  }
  return query;
}
```

## Type Contracts

Frontend API query types should mirror the backend contract, not temporary UI state. If a clearable control uses `""` locally, keep that type in the page state and convert it before calling the API wrapper.

## Tests Required

For bug fixes around request parameters, add a unit test that asserts the API wrapper omits empty values and keeps valid selected filters.
