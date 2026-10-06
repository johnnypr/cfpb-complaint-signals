PY ?= python
export PYTHONPATH := src

.PHONY: install pipeline analysis test all
install:
	$(PY) -m pip install -r requirements.txt
pipeline:   ## download archive (~1.3 GB zipped), filter, topic model, SQL signals (~5-8 min)
	$(PY) -m cfpbsignals.pipeline
analysis:   ## statistics + charts -> reports/
	$(PY) -m cfpbsignals.analysis
test:
	$(PY) -m pytest -q
all: pipeline analysis test
