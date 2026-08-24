# Set the default recipe to list all available commands
default:
    @just --list

# Create and/or update the lockfile with the latest packages. Note that the "--exclude-newer 7d" option will be added when released.
lock:
  pdm lock --exclude-newer 7d

# Install/sync packages in the virtual environment
sync:
  pdm sync --clean

# Install frontend JS dependencies
frontend-install:
    cd frontend && pnpm install

# Build the frontend JS/CSS bundles into the Django static directory
frontend-build:
    cd frontend && pnpm run build && pnpm run build-content

# Install Playwright browser binaries needed for the e2e tests
playwright-install:
    pdm run playwright install

# One-time setup for a fresh clone: installs Python + JS deps, builds the frontend
# assets, installs Playwright browsers, and applies migrations.
# Prerequisites (not installed by this recipe):
#   - just, pdm, and pnpm must already be installed and on PATH
#   - node must be on PATH too - a standalone pnpm install doesn't expose one,
#     so run `pnpm env use --global lts` first if `node --version` fails
bootstrap: sync frontend-install frontend-build playwright-install migrate

# Run the Django development server
run:
    pdm run example/manage.py runserver

# Make migrations
makemigrations:
    pdm run example/manage.py makemigrations

# Apply migrations
migrate:
    pdm run example/manage.py migrate

# Create a superuser
createsuperuser:
    pdm run example/manage.py createsuperuser

# Collect static files
collectstatic:
    pdm run example/manage.py collectstatic

# Run Django shell
shell:
    pdm run example/manage.py shell

# Check for any problems in your project
check:
    pdm run example/manage.py check

# Generic manage command
manage *ARGS:
    pdm run example/manage.py {{ARGS}}

# Run the full test suite, including the Playwright browser tests
test *ARGS:
    pdm run pytest {{ARGS}}

# Run only the fast Python tests (skips the Playwright browser tests)
test-fast *ARGS:
    pdm run pytest -m "not e2e" {{ARGS}}

# Install pre-commit hooks
pc-install:
    pre-commit install

# Upgrade pre-commit hooks
pc-up:
    pre-commit autoupdate

# Run pre-commit hooks
pc-run:
    pre-commit run --all-files
