.PHONY: help test test-unit test-integration test-coverage lint format clean

help:
	@echo "Available commands:"
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests"
	@echo "  make test-coverage     - Run with coverage report"
	@echo "  make lint              - Lint code"
	@echo "  make format            - Format code"
	@echo "  make clean             - Clean artifacts"

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v 2>/dev/null || pytest tests/ -k "TestTools or TestStateManager" -v

test-integration:
	pytest tests/integration/ -v 2>/dev/null || pytest tests/ -k "TestEndToEndWorkflow" -v

test-coverage:
	pytest tests/ --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80

lint:
	pylint src/ lambda/ --disable=C0114,C0115,C0116 2>/dev/null || echo "pylint not installed"

format:
	black src/ tests/ lambda/ 2>/dev/null || echo "black not installed"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov/
