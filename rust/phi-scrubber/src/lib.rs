//! PHI scrubber for clinical notes.
//!
//! The pattern table is `shared/phi_patterns.json`, embedded at compile time,
//! so the Rust and Python scrubbers run the same patterns in the same order.
//! `tests/parity.rs` runs the shared fixtures that the Python suite also runs.
//!
//! Used where the Python service is not in the path: the n8n intake workflow
//! and batch de-identification jobs call the `phi-scrub` binary.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use regex::Regex;
use serde::{Deserialize, Serialize};

const PATTERNS_JSON: &str = include_str!("../../../shared/phi_patterns.json");

#[derive(Deserialize)]
struct PatternFile {
    version: String,
    patterns: Vec<RawPattern>,
}

#[derive(Deserialize)]
struct RawPattern {
    kind: String,
    regex: String,
    replacement: String,
}

struct Pattern {
    kind: String,
    regex: Regex,
    replacement: String,
}

struct Compiled {
    version: String,
    patterns: Vec<Pattern>,
}

fn compiled() -> &'static Compiled {
    static C: OnceLock<Compiled> = OnceLock::new();
    C.get_or_init(|| {
        let file: PatternFile =
            serde_json::from_str(PATTERNS_JSON).expect("shared/phi_patterns.json is valid JSON");
        let patterns = file
            .patterns
            .into_iter()
            .map(|p| Pattern {
                regex: Regex::new(&p.regex)
                    .unwrap_or_else(|e| panic!("pattern {} does not compile: {e}", p.kind)),
                kind: p.kind,
                replacement: p.replacement,
            })
            .collect();
        Compiled { version: file.version, patterns }
    })
}

/// Result of scrubbing one note. `counts` is keyed by PHI kind and is safe to log.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ScrubResult {
    pub text: String,
    pub counts: BTreeMap<String, usize>,
    pub patterns_version: String,
}

impl ScrubResult {
    pub fn total(&self) -> usize {
        self.counts.values().sum()
    }
}

/// Replace PHI with typed placeholders, applying patterns in table order.
pub fn scrub(input: &str) -> ScrubResult {
    let c = compiled();
    let mut text = input.to_string();
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    for p in &c.patterns {
        let n = p.regex.find_iter(&text).count();
        if n > 0 {
            text = p.regex.replace_all(&text, p.replacement.as_str()).into_owned();
            *counts.entry(p.kind.clone()).or_insert(0) += n;
        }
    }
    ScrubResult { text, counts, patterns_version: c.version.clone() }
}

pub fn patterns_version() -> &'static str {
    &compiled().version
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_patterns_compile() {
        assert!(compiled().patterns.len() >= 10);
        assert!(patterns_version().starts_with("phi-patterns-"));
    }

    #[test]
    fn group_reference_replacement() {
        let r = scrub("MRN: 00482913 admitted");
        assert_eq!(r.text, "MRN: [MRN] admitted");
        assert_eq!(r.total(), 1);
    }
}
