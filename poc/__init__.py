"""Proof-of-Change core: verdict rules and the deterministic main-vs-PR comparison.

Models (Nemotron) extract claims, write probes and label findings. They never decide whether two outputs are equal
and never compute the PR verdict: both are plain code in this package.
"""
