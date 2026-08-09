"""Digital Patwari beta user interface.

This package is a THIN presentation layer. It contains no domain rules:
every ownership, area, mutation, validation and reconciliation decision is
delegated to the canonical engines in ``digital_patwari/``. Nothing here
may re-derive a share, an area, or a legal conclusion.

Layers:

- ``page_render``  synthetic, privacy-safe Fard page images (SVG) plus the
                   evidence-region coordinates that reference them.
- ``fixtures``     representative complete/warning/partial/failed documents,
                   fed through the REAL pipeline via a provider that
                   satisfies ``digital_patwari.extraction.ExtractionProvider``
                   and never touches the network.
- ``viewmodels``   typed DTOs converting canonical objects into UI shapes.
- ``ask``          typed adapter boundary for "Ask Digital Patwari".
- ``sessions``     session store and the extraction-backend boundary.
- ``api``          framework-free JSON routing.
- ``server``       local development server.
"""
