---
id: LAB-GEN-002
title: Lynch Syndrome Germline Testing (MLH1, MSH2, MSH6, PMS2, EPCAM)
version: "2026.1"
effective: "2026-01-01"
cpt_codes: ["81292", "81295", "81298", "81317", "81435"]
criteria:
  - id: genetic_counseling
    group: required
    text: Pre-test genetic counseling by a qualified provider is documented.
    offline_patterns:
      - "genetic counsel(?:ing|or|ed)"
      - "pre-?test counsel(?:ing|ed)"
  - id: tumor_screening_abnormal
    group: indication
    text: Tumor screening shows MSI-high or loss of a mismatch repair protein (MLH1, MSH2, MSH6 or PMS2) on IHC, without MLH1 promoter hypermethylation or BRAF V600E.
    offline_patterns:
      - "\\bMSI[- ]?(?:H|high)\\b"
      - "\\bmicrosatellite instability[- ]high\\b"
      - "\\b(?:loss of|absent)\\s+(?:MLH1|MSH2|MSH6|PMS2)(?:\\s*(?:/|and)\\s*(?:MLH1|MSH2|MSH6|PMS2))*\\b[^.;]*\\b(?:IHC|immunohistochemistry|staining|expression)"
      - "\\bdeficient mismatch repair\\b|\\bdMMR\\b"
  - id: personal_early_lynch_cancer
    group: indication
    text: Personal history of colorectal or endometrial cancer diagnosed before age 50.
    offline_exclude:
      - "\\b(?:mother|father|sister|brother|daughter|son|aunt|uncle|niece|nephew|cousin|grandmother|grandfather|relative|family history)\\b"
    offline_patterns:
      - "(?<!family )(?:diagnosed with|history of|dx of)\\s+(?:[\\w-]+\\s+){0,3}(?:colorectal|colon|rectal|endometrial|uterine) (?:cancer|adenocarcinoma|carcinoma)\\b[^.;]*?\\bat (?:age )?(?:[1-4]\\d)\\b"
  - id: family_lynch_history
    group: indication
    text: A first-degree relative with a Lynch-associated cancer diagnosed before age 50, or a relative with a known Lynch syndrome pathogenic variant.
    offline_patterns:
      - "\\b(?:mother|father|sister|brother|daughter|son)\\b[^.;]*\\b(?:colorectal|colon|endometrial|uterine) cancer\\b[^.;]*?\\bat (?:age )?(?:[1-4]\\d)\\b"
      - "\\b(?:mother|father|sister|brother|daughter|son|aunt|uncle|cousin)\\b[^.;]*\\b(?:Lynch syndrome|MLH1|MSH2|MSH6|PMS2) (?:pathogenic variant|mutation|carrier)"
---

## Overview

Lynch syndrome is the most common inherited colorectal cancer syndrome and also raises risk of endometrial, ovarian, gastric and urinary tract cancers. Identifying carriers allows colonoscopy every one to two years and cascade testing of relatives.

## Coverage criteria

Germline testing is medically necessary when BOTH are documented:

1. Pre-test genetic counseling by a qualified provider.
2. At least ONE of the following:
   - Tumor screening (MSI or IHC) of a colorectal or endometrial cancer shows MSI-high or loss of MLH1, MSH2, MSH6 or PMS2 expression, and for isolated MLH1 loss, MLH1 promoter hypermethylation and BRAF V600E have been excluded.
   - Personal history of colorectal or endometrial cancer diagnosed before age 50.
   - A first-degree relative with a Lynch-associated cancer diagnosed before age 50, or any relative with a known Lynch syndrome pathogenic variant.

## Documentation requirements

Include the tumor screening report or a summary of MSI/IHC results, ages at diagnosis, and the relationship of affected relatives.

## Not medically necessary

Population screening without personal or family history, and germline testing when isolated MLH1 loss is explained by promoter hypermethylation.

## Codes

CPT 81292 (MLH1 full sequence), 81295 (MSH2 full sequence), 81298 (MSH6 full sequence), 81317 (PMS2 full sequence), 81435 (hereditary colon cancer panel).
