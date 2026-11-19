//! `phi-scrub`: read a note on stdin, write the scrubbed note to stdout.
//!
//!   phi-scrub < note.txt            # scrubbed text
//!   phi-scrub --json < note.txt     # {"text": ..., "counts": {...}, "patterns_version": ...}
//!
//! Counts go to stderr in text mode so pipelines can audit without seeing PHI.

use std::io::{self, Read, Write};

fn main() -> io::Result<()> {
    let json = std::env::args().any(|a| a == "--json");
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let result = phi_scrubber::scrub(&input);
    let mut out = io::stdout().lock();
    if json {
        serde_json::to_writer(&mut out, &result).map_err(io::Error::other)?;
        writeln!(out)?;
    } else {
        out.write_all(result.text.as_bytes())?;
        eprintln!(
            "phi-scrub: {} redactions {:?} ({})",
            result.total(),
            result.counts,
            result.patterns_version
        );
    }
    Ok(())
}
