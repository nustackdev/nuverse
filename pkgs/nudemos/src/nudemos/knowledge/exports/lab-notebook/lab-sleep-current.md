---
title: Sleep current, regression and fix
tags: [battery, firmware, test]
updated: -22
owner: theo
---
Power analyzer, 12 h runs, 5 units per build. Probe in damp loam, gateway in range.

## Numbers

| Build | Mean | Range |
|---|---|---|
| 2.2.4 (v1 ship) | 19.3 uA | 18.8 to 20.1 |
| 2.3.0 | 31.0 uA | 29.6 to 32.4 |
| 2.3.2 (fix) | 18.1 uA | 17.4 to 18.9 |

## Cause
2.3.0 left the I2C pull-ups on in sleep and the probe excitation pin floating. About 13 uA between them. @ravi found it in an afternoon once we had the trace.

## Budget at 15 min interval (2.3.2)
```
sleep     18 uA x 24 h          = 0.43 mAh/day
wakes     96 x 0.055 mAh        = 5.28 mAh/day
total                           = 5.71 mAh/day
usable    2600 mAh x 0.93       = 2420 mAh
life      2420 / 5.71           = 424 days, about 14 months
```

Batch spot-check limit on the [[shipping-checklist]] is 22 uA. Project page: [[battery-push]]. Aging side: [[lab-cell-aging]].

- [x] Add pin states to the pre-sleep checklist in firmware @ravi due:-20
