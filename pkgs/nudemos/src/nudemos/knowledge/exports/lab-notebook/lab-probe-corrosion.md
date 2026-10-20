---
title: Probe corrosion, salt fog
tags: [probe, test]
updated: -18
owner: theo
---
v1 returns showed pitting at the soil line after one season. Tested v3 probe boards: bare ENIG electrodes vs conformal coated.

## Setup
96 h neutral salt fog, 35 C. 6 bare, 6 coated. Readings in a reference loam at 25% VWC before and after, probe inserted to {{probe-depth}}.

## Results

| | Visible pitting | Reading drift after 96 h |
|---|---|---|
| Bare ENIG | 3 of 6, all at the soil line | +4.1% VWC |
| Coated | 0 of 6 | +0.6% VWC |

## Observations
- Pitting starts exactly where air, water and soil meet. The coating has to run past the depth line, not stop at it.
- Coating adds 0.4 pF to the electrode. Small, but the curves need a redo, see [[lab-calibration]].

## Decision
Coat to the depth line plus 2 cm on all v3 probes. Batch check added to the [[shipping-checklist]]. Enclosure side in [[lab-enclosure-v3]].

- [x] Order the coated probe batch @theo due:-12
