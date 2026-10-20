---
title: Cell aging test, week 6
tags: [battery, test]
updated: -3
owner: theo
---
Setup: 12 x Cell A (2600 mAh), 12 x Cell B (2500 mAh), oven at 45 C. Load mimics a wake cycle: 80 mA for 2.5 s every 60 s, 18 uA between. Compresses about 15x. For [[d05-second-cell]].

## Week 6

| | Week 0 | Week 6 |
|---|---|---|
| Cell A, V under pulse | 3.52 V | 3.41 V |
| Cell B, V under pulse | 3.50 V | 3.44 V |
| Cell A, first-pulse dip after 24 h rest | 3.31 V, 60 ms | 3.05 V, 210 ms |
| Cell B, first-pulse dip after 24 h rest | 3.33 V, 30 ms | 3.21 V, 40 ms |

## Observations
- Passivation on Cell A is growing. Cell B barely moves.
- Brownout is 2.90 V. Neither cell close yet, but Cell A margin went from 410 mV to 150 mV.
- No leaks, no swelling. One Cell A label peeled, cosmetic.

Still consistent with the {{battery-life}} claim at room temperature. Cold is the problem, see [[lab-cold-chamber]]. Cell sourcing in [[lab-supplier-calls]].

- [ ] Week 8 readout, then pull 4 cells of each for capacity @theo due:+14
- [ ] Check brownout margin for the Cell A first-pulse dip in firmware @ravi due:+5
