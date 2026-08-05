# QueryPilot — Backend

QueryPilot is a Spring Boot backend for translating natural language into SQL. This repository currently contains the **Sprint 1.1 foundation**: project skeleton, package structure, build configuration, and environment-based configuration. No business logic, entities, or APIs have been implemented yet — those land in later sprints.

## Project Overview

- **Status:** Foundation (Sprint 1.1) — no business logic yet.
- **Package root:** `com.querypilot`
- **Build tool:** Maven

## Tech Stack

| Concern            | Choice                              |
|---------------------|--------------------------------------|
| Language            | Java 21                             |
| Framework           | Spring Boot 3.2.4                   |
| Web                 | Spring Boot Starter Web             |
| Validation          | Spring Boot Starter Validation      |
| Security            | Spring Boot Starter Security        |
| Persistence         | Spring Boot Starter Data JPA        |
| Database            | PostgreSQL                          |
| Boilerplate         | Lombok                              |
| Dev experience      | Spring Boot DevTools                |
| Testing             | Spring Boot Starter Test, Spring Security Test |
| Build tool          | Maven                               |

## Prerequisites

- **Java 21+** — [Adoptium downloads](https://adoptium.net/)
- **Maven 3.8+** — [Install guide](https://maven.apache.org/install.html)
- **PostgreSQL 14+** — running locally or reachable via network, for the `dev`/`prod` profiles

## Project Structure

```
backend/
├── pom.xml
├── README.md
└── src/
    ├── main/
    │   ├── java/com/querypilot/
    │   │   ├── config/          # Spring configuration classes
    │   │   ├── controller/      # REST controllers
    │   │   ├── dto/
    │   │   │   ├── request/     # Inbound request DTOs
    │   │   │   └── response/    # Outbound response DTOs
    │   │   ├── entity/          # JPA entities
    │   │   ├── repository/      # Spring Data JPA repositories
    │   │   ├── service/         # Service interfaces
    │   │   │   └── impl/        # Service implementations
    │   │   ├── security/        # Security configuration
    │   │   ├── exception/       # Custom exceptions & handlers
    │   │   ├── util/            # Shared utilities
    │   │   ├── mapper/          # Entity <-> DTO mappers
    │   │   ├── constant/        # Application constants
    │   │   ├── client/          # External service clients
    │   │   ├── prompt/          # Prompt templates for NL2SQL
    │   │   └── QueryPilotApplication.java
    │   └── resources/
    │       ├── application.yml
    │       ├── application-dev.yml
    │       └── application-prod.yml
    └── test/
        └── java/com/querypilot/
            └── QueryPilotApplicationTests.java
```

## Configuration

All configuration is environment-driven — no secrets are hardcoded. The active profile is selected via `SPRING_PROFILES_ACTIVE` (defaults to `dev`).

| Variable                    | Used in    | Description                          | Dev default                                   |
|------------------------------|-----------|----------------------------------------|------------------------------------------------|
| `SPRING_PROFILES_ACTIVE`     | common    | Active Spring profile (`dev`/`prod`)   | `dev`                                           |
| `SERVER_PORT`                 | common    | HTTP port                              | `8080`                                          |
| `SPRING_DATASOURCE_URL`       | dev/prod  | JDBC URL for PostgreSQL                | `jdbc:postgresql://localhost:5432/querypilot_dev` |
| `SPRING_DATASOURCE_USERNAME`  | dev/prod  | Database username                      | `postgres`                                      |
| `SPRING_DATASOURCE_PASSWORD`  | dev/prod  | Database password                      | `postgres`                                      |

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
java -jar target/querypilot-1.0-SNAPSHOT.jar
```

### 4. Test

```sh
mvn test
```

## Roadmap

This sprint covers the foundation only. Authentication (JWT), AES encryption, database metadata introspection, Gemini integration, query history, and SQL execution are scoped for subsequent sprints.
