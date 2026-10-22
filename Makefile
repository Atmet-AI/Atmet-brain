.PHONY: test check demo schema wheel
test:
	python -m unittest discover -s tests -v
check:
	python scripts/check_project.py
demo:
	python examples/demo.py
	python examples/automation_demo.py
schema:
	python scripts/generate_openapi.py
wheel:
	python -m pip wheel --no-deps . -w dist
