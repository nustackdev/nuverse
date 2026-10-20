---
title: Antenna tuning, v3 cap
tags: [radio, antenna, test]
updated: -16
owner: theo
---
Range dropped with the v3 cap. VNA showed why.

## Bench
- v2 cap: resonance at 868 MHz, return loss -16 dB.
- v3 cap: resonance moved to 851 MHz. At 868 MHz return loss only -7 dB.
- Swapped the shunt cap in the match from 1.5 pF to 1.0 pF. Back to 867 MHz, -14 dB at 868.
- Wet soil 5 cm below the cap pulls it about 3 MHz further down. Tuned with the probe in damp loam, not in air.

## Field, gateway on a 4 m pole, SF10, +14 dBm

| Distance | Setting | RSSI |
|---|---|---|
| 500 m | open field | -96 dBm |
| 2 km | open field | -114 dBm |
| 600 m | through hedges and two houses | -118 dBm |

All decoded. Matches {{gateway-range}} and the reasoning in [[d01-lora]]. Enclosure details in [[lab-enclosure-v3]].

## Next
Close probes waste airtime at SF10. That is the adaptive data rate win for [[battery-push]].

- [ ] Drop to SF8 when link margin is above 10 dB, ring 0 first @ravi due:+4
