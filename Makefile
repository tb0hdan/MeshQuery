all: lint mypy test

lint:
	@pylint -r y -j 0 src/

mypy:
	@mypy --check-untyped-defs --disallow-untyped-defs src/

test:
	@pytest --cov src/
