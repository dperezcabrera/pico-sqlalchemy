# AI Coding Skills

[Claude Code](https://code.claude.com) and [OpenAI Codex](https://openai.com/index/introducing-codex/) skills for AI-assisted development with pico-sqlalchemy.

## Installation

```bash
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash -s -- sqlalchemy
```

Or install all pico-framework skills:

```bash
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash
```

### Platform-specific

```bash
# Claude Code only
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash -s -- --claude sqlalchemy

# OpenAI Codex only
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash -s -- --codex sqlalchemy
```

## Available Commands

### `/add-repository`

Creates a SQLAlchemy entity and repository with pico-sqlalchemy. Use when adding database models, declarative query repositories, or transactional service layers.

**Generates:** entity class with `mapped_column`, repository with `@repository` + declarative queries, service with `@transactional` methods.

```
/add-repository Product
/add-repository Order --with-service
```

### `/add-component`

Creates a new pico-ioc component with dependency injection. Use when adding services, factories, or interceptors.

```
/add-component ProductService
```

### `/add-tests`

Generates tests for existing pico-framework components. Creates integration tests with in-memory database for repositories and unit tests for services.

```
/add-tests ProductRepository --integration
/add-tests ProductService
```

## More Information

See [pico-skills](https://github.com/dperezcabrera/pico-skills) for the full list of skills, selective installation, and details.
