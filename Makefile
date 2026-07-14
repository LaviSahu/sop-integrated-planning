.PHONY: demo test dashboard clean

PYTHON ?= python3
export PYTHONPATH := src

demo:
	$(PYTHON) -m sop_integrated_planning demo

test:
	$(PYTHON) -m unittest discover -s tests -v

dashboard:
	$(PYTHON) -m sop_integrated_planning dashboard

clean:
	rm -rf output/*.json output/*.html
	find . -type d -name '__pycache__' -not -path './.git/*' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
