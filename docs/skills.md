# Claude Code Skills

[Claude Code](https://code.claude.com) skills for AI-assisted development with pico-sqlalchemy.

## Installation

```bash
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash -s -- sqlalchemy
```

Or install all pico-framework skills:

```bash
curl -sL https://raw.githubusercontent.com/dperezcabrera/pico-skills/main/install.sh | bash
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/add-repository` | Add SQLAlchemy entities and repositories with transactions |
| `/add-component` | Add components, factories, interceptors, settings |
| `/add-tests` | Generate tests for pico-framework components |

## Usage

```
/add-repository Product
/add-component ProductService
/add-tests ProductRepository
```

## More Information

See [pico-skills](https://github.com/dperezcabrera/pico-skills) for the full list of skills, selective installation, and details.
