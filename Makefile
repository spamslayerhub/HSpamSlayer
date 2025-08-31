install:
	@pipenv install --dev

shell:
	@pipenv shell

tests:
	@pipenv run python3 -m pytest --verbose tests/

run:
	@pipenv run python3 src/main.py

.PHONY: tests run install shell
