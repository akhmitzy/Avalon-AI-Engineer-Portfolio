---
id: LAB-PGX-003
title: CYP2C19 Genotyping for Clopidogrel Therapy
version: "2026.1"
effective: "2026-01-01"
cpt_codes: ["81225"]
criteria:
  - id: clopidogrel_planned
    group: required
    text: Clopidogrel is being started or is planned, or the patient is currently taking it.
    offline_patterns:
      - "\\b(?:clopidogrel|plavix)\\b"
  - id: cardiovascular_indication
    group: indication
    text: Acute coronary syndrome, percutaneous coronary intervention (PCI) with stent, or recent ischemic stroke or TIA.
    offline_patterns:
      - "\\b(?:acute coronary syndrome|ACS|NSTEMI|STEMI|myocardial infarction)\\b"
      - "\\b(?:PCI|percutaneous coronary intervention|drug-eluting stent|DES|stent placement|stented)\\b"
      - "\\b(?:ischemic stroke|TIA|transient ischemic attack)\\b"
---

## Overview

CYP2C19 loss-of-function alleles (*2, *3) reduce activation of clopidogrel. Poor and intermediate metabolizers have higher rates of stent thrombosis and recurrent events and may benefit from prasugrel or ticagrelor.

## Coverage criteria

CYP2C19 genotyping is medically necessary when BOTH are documented:

1. Clopidogrel is being started, is planned, or is currently prescribed.
2. The indication is acute coronary syndrome, PCI with stent placement, or a recent ischemic stroke or transient ischemic attack.

## Documentation requirements

Name the antiplatelet agent and the cardiovascular or cerebrovascular indication with the date of the event or procedure.

## Not medically necessary

Genotyping when clopidogrel is not being considered, routine preemptive panel testing without a current indication, and repeat genotyping.

## Codes

CPT 81225 (CYP2C19 common variants).
