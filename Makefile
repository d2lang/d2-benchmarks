PYTHON ?= python3

.PHONY: setup doctor validate test bench
setup:
	$(PYTHON) scripts/setup.py
doctor:
	$(PYTHON) -m benchmarks doctor
validate:
	$(PYTHON) -m benchmarks validate
test:
	$(PYTHON) -m unittest discover -s tests -v
bench:
	./make.sh
