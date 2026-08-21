# Senza Agent Core and Plugins

Senza is the Python assembly surface for the Rust Runtime Agent Core. The Core
owns the Run, Turn, Model, Tool, and settled lifecycle. A Plugin packages tools
and hooks for reuse. Hook locations are twelve fixed lifecycle boundaries
defined by the Core; a Plugin cannot choose an arbitrary source-code position.
