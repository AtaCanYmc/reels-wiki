# Contributing

## Setup

```bash
make install-dev
```

## Running Tests

```bash
make test
```

## Branch Naming

Use short, descriptive branch names prefixed by type:

- `feat/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `refactor/<short-name>`

## Commit Format

Follow Conventional Commits:

```text
<type>(<scope>): <subject>
```

Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

## Pull Request Checklist

- [ ] Tests pass locally via `make test`.
- [ ] No real API keys, tokens, or personal vault paths are committed.
- [ ] Documentation is updated if CLI flags, config keys, or entry points changed.
