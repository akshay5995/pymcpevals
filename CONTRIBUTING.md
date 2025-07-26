# Contributing to PyMCPEvals

First off, thank you for considering contributing to PyMCPEvals! It's people like you that make the open-source community such a great place.

This document provides guidelines for contributing to the project. Please read it carefully to ensure a smooth and effective contribution process.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- `pip` for package management
- `git` for version control

### Setting Up the Development Environment

1.  **Fork the repository:** Start by forking the [main repository](https://github.com/akshay5995/pymcpevals) on GitHub.

2.  **Clone your fork:**
    ```bash
    git clone https://github.com/akshay5995/pymcpevals.git
    cd pymcpevals
    ```

3.  **Create a virtual environment:** It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

4.  **Install dependencies:** The project uses `setuptools` for packaging. Install the project in "editable" mode with the `dev` dependencies.
    ```bash
    pip install -e ".[dev]"
    ```
    This command installs all the necessary packages for development, including `pytest`, `black`, `ruff`, and `mypy`.

## Running Tests

The project uses `pytest` for testing.

1.  **Run all tests:**
    ```bash
    pytest
    ```

2.  **Run tests with coverage:**
    ```bash
    pytest --cov=src/pymcpevals --cov-report=term-missing
    ```

3.  **Run tests for a specific file:**
    ```bash
    pytest tests/test_some_feature.py
    ```

## Code Style and Linting

We use `black` for code formatting and `ruff` for linting to maintain a consistent code style.

1.  **Format your code:** Before committing, run `black` to format your code automatically.
    ```bash
    black src tests
    ```

2.  **Check for linting errors:** Run `ruff` to identify potential issues.
    ```bash
    ruff check src tests
    ```

## Type Checking

We use `mypy` for static type checking. Ensure your code passes `mypy` checks before submitting a pull request.

```bash
mypy src
```

## Submitting Changes

1.  **Create a new branch:**
    ```bash
    git checkout -b feature/your-new-feature
    ```

2.  **Make your changes:** Add your new feature or fix the bug.

3.  **Add and commit your changes:**
    ```bash
    git add .
    git commit -m "feat: Add your descriptive commit message"
    ```
    We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

4.  **Push to your fork:**
    ```bash
    git push origin feature/your-new-feature
    ```

5.  **Open a Pull Request:** Go to the original repository on GitHub and open a pull request from your forked branch. Provide a clear description of the changes you've made.

Thank you for your contribution!
