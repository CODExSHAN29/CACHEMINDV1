.PHONY: help install run test verify benchmark clean docker-up docker-down

help:
	@echo "CacheMind Developer Commands:"
	@echo "  make install     - Install package in editable mode with dev dependencies"
	@echo "  make run         - Run the CacheMind gateway server locally"
	@echo "  make test        - Run complete pytest test suite"
	@echo "  make verify      - Run live system smoke verification"
	@echo "  make benchmark   - Run latency and throughput benchmark"
	@echo "  make docker-up   - Start CacheMind, Redis, and Prometheus in Docker"
	@echo "  make docker-down - Stop Docker Compose services"
	@echo "  make clean       - Remove cached Python bytecode and test artifacts"

install:
	pip install -e ".[dev]"

run:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v

verify:
	python scripts/verify_live.py

benchmark:
	python scripts/benchmark_latency.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
