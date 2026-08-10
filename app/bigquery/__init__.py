"""BigQuery as the system of record.

The detection layer was written against dataclasses precisely so the store could
move. This package is that move: a faithful mirror of every canonical table, a
property graph over the relationships that actually exist, and one place that
knows the project and dataset names.
"""
