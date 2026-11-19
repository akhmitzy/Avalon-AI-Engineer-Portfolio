---
id: LAB-GEN-001
title: Hereditary Breast and Ovarian Cancer (BRCA1/BRCA2) Genetic Testing
version: "2026.2"
effective: "2026-01-01"
cpt_codes: ["81162", "81163", "81165"]
criteria:
  - id: genetic_counseling
    group: required
    text: Pre-test genetic counseling by a qualified provider is documented.
    offline_patterns:
      - "genetic counsel(?:ing|or|ed)"
      - "pre-?test counsel(?:ing|ed)"
  - id: personal_early_breast_cancer
    group: history
    text: Personal history of breast cancer diagnosed at age 50 or younger.
    offline_exclude:
      - "\\b(?:mother|father|sister|brother|daughter|son|aunt|uncle|niece|nephew|cousin|grandmother|grandfather|relative|family history)\\b"
    offline_patterns:
      - "(?<!family )(?:diagnosed with|history of|dx of|dx'd with)\\s+(?:[\\w-]+\\s+){0,3}breast cancer\\b[^.;]*?\\bat (?:age )?(?:[1-4]\\d|50)\\b"
  - id: personal_ovarian_pancreatic_cancer
    group: history
    text: Personal history of epithelial ovarian, fallopian tube, primary peritoneal or exocrine pancreatic cancer at any age.
    offline_exclude:
      - "\\b(?:mother|father|sister|brother|daughter|son|aunt|uncle|niece|nephew|cousin|grandmother|grandfather|relative|family history)\\b"
    offline_patterns:
      - "(?<!family )(?:diagnosed with|history of|dx of)\\s+(?:[\\w-]+\\s+){0,3}(?:ovarian|fallopian tube|primary peritoneal|pancreatic) (?:cancer|carcinoma|adenocarcinoma)"
  - id: family_history
    group: history
    text: A first- or second-degree relative with breast cancer at 50 or younger, ovarian cancer, pancreatic cancer, male breast cancer, or a known BRCA1/BRCA2 pathogenic variant.
    offline_patterns:
      - "\\b(?:mother|sister|daughter|aunt|grandmother|father|brother|niece|cousin)\\b[^.;]*\\b(?:ovarian|pancreatic) cancer"
      - "\\b(?:mother|sister|daughter|aunt|grandmother)\\b[^.;]*\\bbreast cancer\\b[^.;]*?\\bat (?:age )?(?:[1-4]\\d|50)\\b"
      - "\\b(?:father|brother|grandfather|uncle)\\b[^.;]*\\bbreast cancer"
      - "\\b(?:mother|sister|daughter|aunt|father|brother|cousin)\\b[^.;]*\\b(?:BRCA1|BRCA2|BRCA) (?:pathogenic variant|mutation|carrier)"
---

## Overview

Germline testing of BRCA1 and BRCA2 identifies pathogenic variants that raise lifetime risk of breast, ovarian, pancreatic and prostate cancer. Results change surveillance, risk-reducing surgery and treatment (for example PARP inhibitor eligibility).

## Coverage criteria

Testing is medically necessary when BOTH of the following are documented:

1. Pre-test genetic counseling by a qualified provider (certified genetic counselor, medical geneticist, or a clinician with genetics training).
2. At least ONE of the following:
   - Personal history of breast cancer diagnosed at age 50 or younger.
   - Personal history of epithelial ovarian, fallopian tube, primary peritoneal, or exocrine pancreatic cancer at any age.
   - A first- or second-degree relative with breast cancer at 50 or younger, ovarian cancer, pancreatic cancer, or male breast cancer, or a relative with a known BRCA1/BRCA2 pathogenic variant.

## Documentation requirements

The clinical note must state the cancer type and age at diagnosis for personal history, and the relationship, cancer type and age at diagnosis for family history. A counseling note or a statement that counseling occurred, with the date, satisfies criterion 1.

## Known familial variant

When a familial pathogenic variant is known, single-site testing (CPT 81165 is for full sequence; use the targeted code where available) is preferred over full gene analysis.

## Not medically necessary

Testing for the general population without personal or family history, direct-to-consumer testing, and repeat germline testing when a valid prior result exists.

## Codes

CPT 81162 (BRCA1/BRCA2 full sequence and deletion/duplication), 81163 (full sequence), 81165 (BRCA1 full sequence).
