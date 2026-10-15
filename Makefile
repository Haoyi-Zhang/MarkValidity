.PHONY: all test recheck audit-evidence clean-results

OUT ?= .reproduction/results
RESULTS ?= results/current/results
AUDIT_OUT ?= .evidence-audit

all:
	PYTHONPATH=src python3 -B run_all.py --out "$(OUT)"
	COVEWM_RESULTS="$(OUT)" PYTHONPATH=src python3 -B -m unittest discover -s tests -v
	PYTHONPATH=src python3 -B recheck.py --results "$(OUT)"
	COVEWM_RESULTS="$(OUT)" python3 -B -S -m unittest discover -s regressions -v
	python3 -B -S validate_evidence.py --results "$(OUT)" --out "$(AUDIT_OUT)"

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	python3 -B -S -m unittest discover -s regressions -v

audit-evidence:
	python3 -B -S validate_evidence.py --results "$(RESULTS)" --out "$(AUDIT_OUT)"

recheck:
	@test -n "$(OUT_RECHECK)" || (echo "Set OUT_RECHECK to a disposable result copy; recheck updates its manifest." >&2; exit 2)
	PYTHONPATH=src python3 -B recheck.py --results "$(OUT_RECHECK)"

clean-results:
	@echo "Retained results are not a clean target. Remove only your own disposable output explicitly." >&2
	@exit 2
