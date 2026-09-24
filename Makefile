.PHONY: all test recheck clean-results

all:
	PYTHONPATH=src python3 run_all.py --out results
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	PYTHONPATH=src python3 recheck.py --results results

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

recheck:
	PYTHONPATH=src python3 recheck.py --results results

clean-results:
	rm -rf results
