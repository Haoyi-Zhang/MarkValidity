.PHONY: all test recheck audit-evidence clean-results

all:
	PYTHONPATH=src python3 run_all.py --out results
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	PYTHONPATH=src python3 recheck.py --results results
	python3 -B -S -m unittest discover -s regressions -v
	python3 -B -S validate_evidence.py --results results --out .evidence-audit

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	python3 -B -S -m unittest discover -s regressions -v

audit-evidence:
	python3 -B -S validate_evidence.py --out .evidence-audit

recheck:
	PYTHONPATH=src python3 recheck.py --results results

clean-results:
	rm -rf results
