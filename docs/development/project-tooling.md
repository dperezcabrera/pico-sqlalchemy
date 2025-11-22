# Project Tooling

This document describes the build, test, and packaging tooling used by the pico-sqlalchemy project. It covers what the tooling is, how the project is configured, and how to run common developer workflows.

## Overview

- pyproject.toml: Central configuration for build system, package metadata, dependencies, and optional extras. Uses setuptools and setuptools_scm to build and version the package.
- tox.ini: Test automation across multiple Python versions (py310–py314). Provides environments to run the test suite and a dedicated coverage run configured to execute pytest with coverage reporting.

## pyproject.toml

What it is:
- Defines the build system (setuptools) and versioning (setuptools_scm).
- Declares the package name (pico-sqlalchemy), metadata, required dependencies, and optional extras.
- Drives how the project is built (sdist and wheel) and how it is installed by pip.

Key points:
- Versioning is automatic via setuptools_scm, typically derived from Git tags.
- Optional extras include an “async” extra to install asynchronous-related dependencies used by the project’s async features and tests.

How to use it:
- Install the package from source:
  ```
  pip install .
  ```
- Editable install for local development:
  ```
  pip install -e .
  ```
- Install with optional async extras:
  ```
  pip install ".[async]"
  ```
  Or when installing from PyPI:
  ```
  pip install "pico-sqlalchemy[async]"
  ```

Versioning and releases:
- Versions are managed by setuptools_scm from your Git tags.
- To prepare a release, tag the commit you want to release:
  ```
  git tag -a v0.1.0 -m "Release v0.1.0"
  git push --tags
  ```
  Building after tagging will produce artifacts with the tagged version.

Building distributions:
- Ensure you have the build tool installed:
  ```
  pip install build
  ```
- Build sdist and wheel:
  ```
  python -m build
  ```
- Artifacts will be written to the dist/ directory.

Uploading to PyPI (optional):
- Check artifacts:
  ```
  pip install twine
  twine check dist/*
  ```
- Upload:
  ```
  twine upload dist/*
  ```

## tox.ini

What it is:
- A tox configuration to run tests across multiple Python interpreters (py310, py311, py312, py313, py314).
- Ensures the test environments install required dependencies, including the “async” extras.
- Provides a coverage environment to execute pytest with coverage reporting.

Prerequisites:
- Install tox:
  ```
  pip install tox
  ```
  Using pipx is recommended for isolation:
  ```
  pipx install tox
  ```
- Ensure the targeted Python versions are installed and discoverable (e.g., via pyenv or system packages).

Common tasks:

- Run the test suite across all configured Python versions:
  ```
  tox
  ```
- Run tests for a single interpreter:
  ```
  tox -e py311
  ```
- Pass arguments through to pytest:
  ```
  tox -e py311 -- -q
  ```
- Run coverage:
  ```
  tox -e coverage
  ```
  The coverage environment will run pytest with coverage enabled and report results to the console. A coverage data file (e.g., .coverage) may be generated for further reporting.

- Speed up by running environments in parallel:
  ```
  tox -p auto
  ```

Notes:
- Tox environments install the project along with the async extras so async-related tests and functionality are available.
- If tox fails due to missing interpreters, install them (e.g., via pyenv) and ensure they’re on PATH.

## Typical Development Workflow

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # on Windows: .venv\Scripts\activate
   ```

2. Install the project (editable) and optional extras if needed:
   ```
   pip install -e ".[async]"
   ```

3. Run tests quickly via pytest (single environment):
   ```
   pip install pytest
   pytest
   ```

4. Validate across all supported Python versions using tox:
   ```
   tox
   ```

5. Generate a coverage report:
   ```
   tox -e coverage
   ```

6. Build release artifacts:
   ```
   pip install build
   python -m build
   ```

7. Tag and publish (when ready):
   ```
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push --tags
   pip install twine
   twine upload dist/*
   ```

## Troubleshooting

- Missing Python interpreters in tox:
  - Install the required versions (py310–py314) using pyenv or your OS package manager.
  - Recreate tox environments:
    ```
    tox -r
    ```

- Version appears as a dirty or local version:
  - Ensure you have a clean working tree and a proper Git tag for the release commit.
  - setuptools_scm uses Git metadata; verify the repository is not shallow and tags are available locally.