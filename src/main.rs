//! PMO - A simple process manager
//!
//! Command-line entry point

fn main() {
    let exit_code = pmo::cli::run().unwrap_or(1);
    std::process::exit(exit_code);
}
