---
title: Calibration curves, three soils
tags: [probe, calibration, test]
updated: -11
owner: theo
---
Raw capacitance counts vs gravimetric VWC. Three soils, 9 moisture steps each, probe at {{probe-depth}}, coated v3 boards (see [[lab-probe-corrosion]]).

## Fit, 3rd order polynomial

| Soil | Range tested | RMSE |
|---|---|---|
| Sandy | 4 to 32% VWC | 1.8% |
| Loam | 8 to 44% VWC | 2.3% |
| Clay | 14 to 52% VWC | 3.9% |

## Observations
- Clay is worse above 40%. The curve flattens, probably salts. Most growers never see that range, and if they do the advice is the same: don't water.
- Loam reference points: field capacity about 30%, wilting point about 12%. Matches the textbook range, good sign.
- Coating shifted raw counts by about 2% across the board. Old v2 curves are wrong for v3 probes.

## Next
Soil type pick goes into first run (talked to Ines, see [[onboarding-redesign]]). Default is loam. Index: [[lab-index]].

- [ ] Ship the three v3 curves in firmware 2.4.2 @ravi due:+11
