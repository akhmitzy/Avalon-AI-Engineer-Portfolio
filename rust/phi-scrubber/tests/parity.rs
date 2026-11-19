//! Parity with the Python scrubber: both run shared/fixtures/phi_cases.json.

use std::collections::BTreeMap;

use serde::Deserialize;

#[derive(Deserialize)]
struct Fixtures {
    cases: Vec<Case>,
}

#[derive(Deserialize)]
struct Case {
    name: String,
    input: String,
    expected: String,
    counts: BTreeMap<String, usize>,
}

fn fixtures() -> Fixtures {
    serde_json::from_str(include_str!("../../../shared/fixtures/phi_cases.json")).unwrap()
}

#[test]
fn shared_fixtures_text_match_python() {
    let mut failures = vec![];
    for c in fixtures().cases {
        let got = phi_scrubber::scrub(&c.input);
        if got.text != c.expected {
            failures.push(format!("{}: expected {:?} got {:?}", c.name, c.expected, got.text));
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

#[test]
fn shared_fixtures_counts_match_python() {
    for c in fixtures().cases {
        assert_eq!(phi_scrubber::scrub(&c.input).counts, c.counts, "{}", c.name);
    }
}

#[test]
fn scrub_is_idempotent() {
    for c in fixtures().cases {
        let once = phi_scrubber::scrub(&c.input).text;
        assert_eq!(phi_scrubber::scrub(&once).text, once, "{}", c.name);
    }
}
