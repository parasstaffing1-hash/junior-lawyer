# Batch 23 · release engineering examples

`run_release_source_gate.py` is the dependency-light CI gate for source correctness. It does not
claim production throughput. Before a production deployment, run `run_http_load.py` against a
representative staging environment and record the result in a release run.

The security baseline is deliberately bounded to Junior Lawyer itself. It does not crawl or probe
third-party systems.
