"""Malaysia LHDN MyInvois e-invoicing integration.

Layered like the storage subsystem so the transport is pluggable:

    einvoice_routes  ── HTTP API (submit / status / cancel / config)
        │
    backends.get_einvoice_backend()  ── stub | direct (chosen by settings)
        │
    ┌───┴────────────────────────────┐
    StubBackend                DirectLHDNBackend
    (offline echo)             ubl_mapper → signer → MyInvoisClient (httpx)

Nothing here reaches the network unless `EINVOICE_BACKEND=direct` and a tenant
has a configured, enabled MyInvoisConfig. The default `stub` backend is what
the test-suite and local dev use.
"""
