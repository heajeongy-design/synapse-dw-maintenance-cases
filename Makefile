PY ?= python3

.PHONY: test repro setup-spark repro-spark

test:
	$(PY) -m unittest discover -s tests -t . -v

repro:
	$(PY) -m tools.record_results

setup-spark:
	$(PY) -m pip install -r requirements.txt

repro-spark:
	$(PY) -m tools.record_results --spark
