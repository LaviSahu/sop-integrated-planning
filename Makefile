.PHONY: demo test dashboard clean

PYTHON ?= python3
export PYTHONPATH := src

demo:
	$(PYTHON) -m sop_integrated_planning demo

test: dashboard
	$(PYTHON) -m unittest discover -s tests -v

# JS-port golden gate only (engine untouched); requires node.
test-js-port: dashboard
	$(PYTHON) -m unittest discover -s tests -p "test_js_port.py" -v

dashboard:
	$(PYTHON) -m sop_integrated_planning dashboard

clean:
	rm -rf output/*.json output/*.html
	find . -type d -name '__pycache__' -not -path './.git/*' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
