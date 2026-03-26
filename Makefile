# Makefile for Talent_Finder_Backend_Sourcing

.PHONY: install lint test run

install:
	pip install -r requirements.txt

lint:
	ruff .
	type-check .
	test .
	test .

run:
	python src/main.py