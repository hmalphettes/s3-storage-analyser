test:
	pytest -s

cov: clean
	pytest --cov=./

clean:
	@rm .coverage .coverage.* &>/dev/null || true

install:
	pip install -r requirements-dev.txt