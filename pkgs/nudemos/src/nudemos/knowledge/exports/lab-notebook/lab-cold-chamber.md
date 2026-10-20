---
title: Cold chamber, Cell A vs Cell B
tags: [battery, test, cold]
updated: -2
owner: theo
---
Chamber at -10 C, 6 units per cell, real firmware, readings every 15 min through a gateway outside the chamber. Week 5 of 6. Note on the chamber door per [[lab-rules]].

## Usable capacity, estimated from voltage curve

| | 20 C | -10 C |
|---|---|---|
| Cell A | 2420 mAh | 2180 mAh |
| Cell B | 2325 mAh | 2250 mAh |

## Projected life at -10 C

| | 0.055 mAh per reading | 0.046 mAh (adaptive data rate) |
|---|---|---|
| Cell A | 12.5 months | 14.8 months |
| Cell B | 12.9 months | 15.2 months |

## Observations
- Without adaptive data rate, neither cell makes it in the cold.
- Side test, 48 h at -20 C: one Cell A unit missed its first wake after a 6 h sleep. Passivation again, matches [[lab-cell-aging]]. Cell B units all woke.

Walked through in [[m-battery-review]]. Feeds [[d05-second-cell]].

- [ ] Add the -20 C side test to the week 6 readout @theo due:+9
