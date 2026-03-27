.PHONY: install test lint format clean help

help:
	@echo "Available targets:"
	@echo "  install       Install dependencies"
	@echo "  test          Run unit tests"
	@echo "  lint          Run code linting (flake8)"
	@echo "  format        Format code (black)"
	@echo "  clean         Remove cache and generated files"
	@echo "  analyze       Run example analysis (requires date args)"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

lint:
	flake8 src/ scripts/ tests/ --max-line-length=100

format:
	black src/ scripts/ tests/ notebooks/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov/
	rm -f data/*.parquet results/*.csv results/*.json results/*.png

analyze:
	python scripts/analyze.py --symbol BTCUSDT --start 2025-02-01 --end 2025-02-08 --output results/
