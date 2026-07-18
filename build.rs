fn main() {
    // On macOS, extension modules need `-undefined dynamic_lookup` so that
    // Python C API symbols are resolved at runtime by the interpreter.
    //
    // Only apply when the `extension-module` feature is enabled (cdylib build).
    // For `cargo test` the feature is off, and the auto-initialize dev-dep
    // links against libpython directly.
    println!("cargo:rerun-if-changed=build.rs");
    if std::env::var("CARGO_FEATURE_EXTENSION_MODULE").is_ok() {
        pyo3_build_config::add_extension_module_link_args();
    }
}
