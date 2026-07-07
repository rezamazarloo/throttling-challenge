# Throttling Challenge

Backend challenge for implementing precise per-user rate limiting in Python and Django.

## Design Decisions

### Why are logs stored with this model?

The challenge asked for request history to be stored, and my understanding was that this history should be persisted in the database. The PDF rules also mentioned that this requirement must be respected. Since there is no separate logging service such as ELK in this project, the most practical option is to keep the request history in the database.

The log records are stored as append-only entries instead of keeping and updating a request counter directly. This avoids possible race conditions that can happen when multiple requests try to update the same counter at the same time. With this structure, request statistics can still be calculated easily using database queries.

### Why was middleware not used?

Middleware would run for every request, even for APIs that may not need throttling. That means each request could trigger an extra database query, which is not ideal for this use case.

If logging was file-based, middleware could be a better fit. However, the challenge asks for throttling per user, not globally, so handling it closer to the relevant API logic gives more control and avoids unnecessary database work.

### Why was token authentication used?

Token authentication was used to keep the authentication part simple, so more time could be spent on the throttling logic and test coverage.

### Why is the user's request count increased only on successful requests?

It does not make sense to reduce a user's available request quota when the service fails for any reason and the user's request is not completed successfully. For that reason, only successful requests are counted.

## Docker

for dev enviroment run `docker-compose up -d --build` to start the required services.
