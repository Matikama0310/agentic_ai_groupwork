.PHONY: help install test test-tools test-state test-workflow test-edges test-e2e test-coverage lint format clean demo server ui

help:
	@echo "NorthStar Agentic Underwriting System"
	@echo "======================================"
	@echo ""
	@echo "Running:"
	@echo "  make demo              - Run CLI demo"
	@echo "  make server            - Start FastAPI server (port 8000)"
	@echo "  make ui                - Launch Streamlit workbench"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-tools        - Run tool tests only"
	@echo "  make test-state        - Run state manager tests"
	@echo "  make test-workflow     - Run workflow node tests"
	@echo "  make test-edges        - Run conditional edge tests"
	@echo "  make test-e2e          - Run end-to-end tests"
	@echo "  make test-coverage     - Run with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Lint code with pylint"
	@echo "  make format            - Format code with black/isort"
	@echo ""
	@echo "Utilities:"
	@echo "  make install           - Install dependencies"
	@echo "  make clean             - Remove build artifacts"
	@echo ""

install:
	pip install -r requirements.txt

# --- Running ---

demo:
	python main.py

server:
	python main.py --server

ui:
	streamlit run app.py

# --- Testing ---

test:
	pytest tests/test_all.py -v

test-tools:
	pytest tests/test_all.py -k "TestDocumentTools or TestDecisionTools or TestDataTools or TestCommsTools" -v

test-state:
	pytest tests/test_all.py::TestStateManager -v

test-workflow:
	pytest tests/test_all.py::TestWorkflowNodes -v

test-edges:
	pytest tests/test_all.py::TestConditionalEdges -v

test-e2e:
	pytest tests/test_all.py::TestEndToEnd -v

test-coverage:
	pytest tests/test_all.py --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
	@echo "Coverage report generated: htmlcov/index.html"

# --- Code Quality ---

lint:
	pylint src/ --disable=C0114,C0115,C0116 2>/dev/null || echo "pylint not installed - run: pip install pylint"

format:
	black src/ tests/ 2>/dev/null || echo "black not installed - run: pip install black"
	isort src/ tests/ 2>/dev/null || echo "isort not installed - run: pip install isort"

# --- Utilities ---

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/
