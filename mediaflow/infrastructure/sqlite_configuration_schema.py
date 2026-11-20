"""The current managed-configuration schema version.

It lives outside the repository module so the shared read-only database
applicability check can compare the marker without importing the repository.
"""

CONFIGURATION_SCHEMA_VERSION = 12
