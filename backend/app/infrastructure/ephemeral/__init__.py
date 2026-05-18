"""Ephemeral provisioning infrastructure (Phase 61 F18).

Spawns a sidecar Docker container per ephemeral environment and copies
source data into it. The :mod:`docker_provisioner` module owns the
container lifecycle; :mod:`data_copy` owns the source→target copy.
"""
