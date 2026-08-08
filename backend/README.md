# QueryPilot — Backend

QueryPilot is a Spring Boot backend for translating natural language into SQL, executing it safely against PostgreSQL, and giving users history, saved queries, and export on top of it. This repository is at **v2.4-RC**: every backend capability through Sprint 2.3 (Export Query Results) is implemented, and this release candidate adds a stabilization pass plus OpenAPI/Swagger documentation ahead of Angular frontend integration.

## Project Overview

- **Status:** v2.4-RC — backend feature-complete, stabilized, and documented; frontend integration is next.
- **Package root:** `com.querypilot`
- **Build tool:** Maven

## Tech Stack

| Concern              | Choice                              |
|-----------------------|--------------------------------------|
| Language              | Java 21                             |
| Framework             | Spring Boot 3.2.4                   |
| Web                   | Spring Boot Starter Web             |
| Validation            | Spring Boot Starter Validation      |
| Security              | Spring Boot Starter Security        |
| Persistence           | Spring Boot Starter Data JPA        |
| Database              | PostgreSQL                          |
| API Documentation     | springdoc-openapi (Swagger UI)      |
| Spreadsheet Export    | Apache POI                          |
| Boilerplate           | Lombok                              |
| Dev experience        | Spring Boot DevTools                |
| Testing               | Spring Boot Starter Test, Spring Security Test, H2 |
| Build tool             | Maven                               |

## Prerequisites

- **Java 21+** — [Adoptium downloads](https://adoptium.net/)
- **Maven 3.8+** — [Install guide](https://maven.apache.org/install.html)
- **PostgreSQL 14+** — running locally or reachable via network, for the `dev`/`prod` profiles
- **A Google Gemini API key** — for SQL generation

## Project Structure

```
backend/
├── pom.xml
├── README.md
└── src/
    ├── main/
    │   ├── java/com/querypilot/
    │   │   ├── client/          # Outbound clients: LLMClient/GeminiClient, MetadataClient/PostgresMetadataClient, DatabaseClient/PostgresDatabaseClient
    │   │   ├── config/          # Spring configuration classes (JWT, Gemini, OpenAPI)
    │   │   ├── constant/        # Application, API, and security constants
    │   │   ├── controller/      # REST controllers
    │   │   ├── dto/
    │   │   │   ├── request/     # Inbound request DTOs
    │   │   │   └── response/    # Outbound response DTOs
    │   │   ├── entity/          # JPA entities
    │   │   ├── exception/       # Custom exceptions & the global @RestControllerAdvice handler
    │   │   ├── export/          # Plain CSV/Excel renderers — not Spring beans
    │   │   ├── mapper/          # Entity <-> DTO mappers
    │   │   ├── prompt/          # Prompt construction for the Prompt Engine
    │   │   ├── repository/      # Spring Data JPA repositories
    │   │   ├── security/        # Security configuration and the JWT filter chain
    │   │   ├── service/         # Service interfaces
    │   │   │   └── impl/        # Service implementations
    │   │   ├── util/            # Shared utilities
    │   │   ├── validator/       # SQL validation
    │   │   └── QueryPilotApplication.java
    │   └── resources/
    │       ├── application.yml
    │       ├── application-dev.yml
    │       └── application-prod.yml
    └── test/
        ├── java/com/querypilot/
        │   └── QueryPilotApplicationTests.java
        └── resources/
            └── application-test.yml
```

## API Overview

All endpoints are versioned under `/api/v1`. Every endpoint except `/auth/register` and `/auth/login` requires a JWT bearer token.

| Domain | Endpoints |
|---|---|
| Authentication | `POST /auth/register`, `POST /auth/login` |
| Metadata | `GET /metadata/schemas`, `GET /metadata/schemas/{schema}`, `GET /metadata/tables/{schema}/{table}`, `GET /metadata/health` |
| Prompt Engine | `POST /prompt/build` |
| Query | `POST /query/generate`, `POST /query/export/csv`, `POST /query/export/excel` |
| Query History | `GET /history`, `GET /history/{id}`, `DELETE /history/{id}` |
| Saved Queries | `POST /saved-queries`, `GET /saved-queries`, `GET /saved-queries/{id}`, `PUT /saved-queries/{id}`, `DELETE /saved-queries/{id}` |

Every JSON response is wrapped in a standard envelope (`success`, `message`, `data`, `timestamp`); the two export endpoints return the file directly as `ResponseEntity<Resource>` with `Content-Disposition: attachment`.

For the full interactive reference — request/response schemas, try-it-out, and JWT authorization — run the app and open Swagger UI (see below).

## API Documentation (Swagger / OpenAPI)

With the application running:

- Swagger UI: `http://localhost:8080/swagger-ui/index.html`
- Raw OpenAPI document: `http://localhost:8080/v3/api-docs`

Both are publicly reachable without a token so the docs themselves can be browsed freely; calling a documented endpoint from Swagger UI's "Try it out" still requires authorizing with a JWT obtained from `/auth/login` via the **Authorize** button.

## Configuration

All configuration is environment-driven — no secrets are hardcoded. The active profile is selected via `SPRING_PROFILES_ACTIVE` (defaults to `dev`).

| Variable                    | Used in    | Description                          | Dev default                                   |
|------------------------------|-----------|----------------------------------------|------------------------------------------------|
| `SPRING_PROFILES_ACTIVE`     | common    | Active Spring profile (`dev`/`prod`)   | `dev`                                           |
| `SERVER_PORT`                 | common    | HTTP port                              | `8080`                                          |
| `SPRING_DATASOURCE_URL`       | dev/prod  | JDBC URL for PostgreSQL                | `jdbc:postgresql://localhost:5432/querypilot_dev` |
| `SPRING_DATASOURCE_USERNAME`  | dev/prod  | Database username                      | `postgres`                                      |
| `SPRING_DATASOURCE_PASSWORD`  | dev/prod  | Database password                      | `postgres`                                      |
| `JWT_SECRET`                  | common    | HS256 signing secret for JWTs          | insecure dev-only fallback (see `application.yml`) |
| `JWT_EXPIRATION`              | common    | Access token lifetime, in milliseconds | `900000` (15 minutes)                           |
| `JWT_ISSUER`                  | common    | JWT `iss` claim                        | `QueryPilot`                                    |
| `GEMINI_API_KEY`              | common    | Google Gemini API key                  | dev-only placeholder — must be overridden       |
| `GEMINI_MODEL`                | common    | Gemini model name                      | `gemini-1.5-flash`                              |
| `GEMINI_ENDPOINT`             | common    | Gemini API base URL                    | `https://generativelanguage.googleapis.com/v1beta/models` |
| `GEMINI_TIMEOUT`              | common    | Gemini request timeout, in milliseconds | `15000`                                        |

In the `prod` profile, the datasource variables have **no defaults** — the application will fail fast at startup if they are not supplied, rather than silently falling back to insecure values.

## Running the Project

### 1. Provision PostgreSQL

Create a database matching your configured URL, e.g.:

```sh
createdb querypilot_dev
```

### 2. Build

```sh
mvn clean install
```

### 3. Run

```sh
mvn spring-boot:run
```

Or run the packaged jar directly:

```sh
java -jar target/querypilot-1.0-SNAPSHOT.jar
```

To run against the `prod` profile with your own database:

```sh
SPRING_PROFILES_ACTIVE=prod \
SPRING_DATASOURCE_URL=jdbc:postgresql://<host>:5432/<db> \
SPRING_DATASOURCE_USERNAME=<user> \
SPRING_DATASOURCE_PASSWORD=<password> \
GEMINI_API_KEY=<key> \
JWT_SECRET=<secret> \
java -jar target/querypilot-1.0-SNAPSHOT.jar
```

### 4. Test

```sh
mvn test
```

Tests run against an in-memory H2 database in PostgreSQL-compatibility mode — no external database is required to run the test suite.

## Roadmap

The backend is feature-complete through this release candidate: foundation, security, authentication, metadata discovery, the Prompt Engine, Gemini-powered SQL generation, SQL validation, SQL execution, query history, saved queries, and CSV/Excel export are all implemented. What's next is an Angular frontend and containerized deployment — see the root [`README.md`](../README.md) for the full roadmap.
