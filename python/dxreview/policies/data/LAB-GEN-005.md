---
id: LAB-GEN-005
title: Cell-Free DNA Prenatal Screening (NIPT)
version: "2026.1"
effective: "2026-01-01"
cpt_codes: ["81420", "81507"]
criteria:
  - id: singleton_pregnancy
    group: required
    text: A confirmed singleton intrauterine pregnancy.
    offline_patterns:
      - "\\bsingleton\\b"
      - "\\bsingle (?:live )?intrauterine pregnancy\\b"
  - id: gestational_age_10_weeks
    group: required
    text: Gestational age of at least 10 weeks at the time of the blood draw.
    offline_patterns:
      - "\\b(?:1\\d|[23]\\d|40)\\s*(?:\\+\\d\\s*)?(?:weeks?|wks?)\\b(?:\\s*(?:\\d\\s*days?\\s*)?(?:gestation|GA|pregnant|by (?:LMP|ultrasound|US)))?"
      - "\\bGA\\s*(?:of\\s*)?(?:1\\d|[23]\\d|40)\\s*(?:w|wk|weeks?)\\b"
---

## Overview

Cell-free DNA screening analyzes placental DNA in maternal plasma to screen for trisomy 21, 18 and 13. It has the highest detection rate of the available aneuploidy screens and is offered to all pregnant patients regardless of age or risk.

## Coverage criteria

Screening is medically necessary when BOTH are documented:

1. A confirmed singleton intrauterine pregnancy.
2. Gestational age of at least 10 weeks at the time of the blood draw.

## Multiple gestation

Twin pregnancies are reviewed individually by a clinician because test performance is lower and not all laboratories validate twin results.

## Documentation requirements

State the number of fetuses and the gestational age with the dating method (LMP or ultrasound).

## Not medically necessary

Screening before 10 weeks, screening for microdeletions or genome-wide copy number in low-risk pregnancies, and repeat screening after a reportable result.

## Codes

CPT 81420 (fetal chromosomal aneuploidy, trisomy 21, 18 and 13), 81507 (fetal aneuploidy with algorithm risk score).
