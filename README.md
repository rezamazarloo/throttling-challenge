# Throttling Challenge

Backend challenge for implementing precise per-user rate limiting in Python and Django.

## Project Brief

Build a system that lets users register a lightweight request, such as sending a message or logging an action, while enforcing a clear rate limit for each individual user.

The main rule is:

- Each user may make at most 5 requests in every 60-second window.
- The limit must be per user, not global.
- If a user exceeds the limit, the API must return an appropriate rejection response.
- The system must keep enough request history of enforced limits.

## General Requirements

- Implement the project with Python and Django.
- API design, data models, and project structure are up to the implementer unless a requirement states otherwise.
- Document important engineering decisions and assumptions.
- Keep the solution testable, explainable, and transparent.
- Code quality, tests, error handling, and clarity are part of the evaluation.
- If any part of the problem is intentionally simplified, explain the simplification clearly.

## Design Decisions To Cover

- How request history is stored.
- The request and response contract.
- The chosen time-window semantics.
- The exact behavior at the 60-second boundary.
- How time-dependent behavior is tested.

## Expected Output

- Executable code.
- A clear explanation of the selected rate-limit semantics.
- Tests for normal and boundary scenarios.

## Minimum Test Cases

- The first 5 requests from a user are allowed.
- The 6th request from the same user is rejected.
- Capacity becomes available again after the time window passes.
- Limits are tracked separately for two different users.
