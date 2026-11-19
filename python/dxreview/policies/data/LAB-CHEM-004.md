---
id: LAB-CHEM-004
title: 25-Hydroxyvitamin D Testing
version: "2026.3"
effective: "2026-03-01"
cpt_codes: ["82306"]
criteria:
  - id: high_risk_condition
    group: indication
    text: A condition that puts the patient at risk of deficiency or bone disease, such as osteoporosis, osteopenia, osteomalacia, malabsorption (celiac disease, Crohn disease, bariatric surgery), chronic kidney disease, chronic liver disease, or hyperparathyroidism.
    offline_patterns:
      - "\\b(?:osteoporosis|osteopenia|osteomalacia|fragility fracture)\\b"
      - "\\b(?:celiac disease|crohn'?s(?: disease)?|malabsorption|gastric bypass|bariatric surgery|sleeve gastrectomy)\\b"
      - "\\b(?:chronic kidney disease|CKD(?: stage)?|cirrhosis|chronic liver disease|hyperparathyroidism)\\b"
  - id: monitoring_known_deficiency
    group: indication
    text: Monitoring of a documented vitamin D deficiency during replacement therapy.
    offline_patterns:
      - "\\b(?:on|started|taking|receiving)\\s+(?:high-dose\\s+)?(?:ergocalciferol|cholecalciferol|vitamin D(?:2|3)?)\\b[^.;]*\\bdeficien"
      - "\\bvitamin D deficiency\\b[^.;]*\\b(?:on|started|taking|receiving|replacement|repletion)\\b"
---

## Overview

25-hydroxyvitamin D is the best marker of vitamin D status. Population screening does not improve outcomes, so testing is limited to patients at risk of deficiency or with bone disease, and to monitoring replacement.

## Coverage criteria

Testing is medically necessary when at least ONE of the following is documented:

- A high-risk condition: osteoporosis, osteopenia, osteomalacia or fragility fracture; malabsorption including celiac disease, Crohn disease, or bariatric surgery; chronic kidney disease; chronic liver disease; or hyperparathyroidism.
- Monitoring of a documented vitamin D deficiency during replacement therapy.

## Frequency

Once per year for high-risk conditions. For monitoring, no more than once every three months during active replacement.

## Not medically necessary

Routine screening of asymptomatic adults, testing for fatigue alone, and testing as part of a wellness panel.

## Codes

CPT 82306 (vitamin D, 25 hydroxy).
