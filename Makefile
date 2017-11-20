test:
	pytest -s

cov: clean
	pytest --cov=./

clean:
	@rm .coverage .coverage.*

install:
	pip install -r requirements-dev.txt