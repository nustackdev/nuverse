# ruff: noqa: RUF001 - the replies are kept as the model wrote them
"""The opening eval runs and probe answers: real answers from Claude, asked for this desk and kept.

Each is one arm of the suite in :mod:`.evals`, put to the model through
Claude Code the way a run launched from the Evals page is, and graded the
same way. Kept so the desk opens with finished runs and nothing is asked
until someone asks.
"""

from __future__ import annotations

from typing import Any


__all__ = ["PROBES", "RUNS"]


RUNS: list[dict[str, Any]] = [
    {
        "key": "b01cldc",
        "model": "claude-sonnet-5",
        "style": "direct",
        "context": "clean",
        "ago": 3.2,
        "seconds": 24.4,
        "by": "Theo Abara",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 3.68,
                "cost": 0.002053,
                "text": "1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 2.52,
                "cost": 0.001328,
                "text": "210",
            },
            "q03": {"got": 13.0, "correct": True, "seconds": 3.48, "cost": 0.001897, "text": "13"},
            "q04": {"got": 12.0, "correct": True, "seconds": 3.55, "cost": 0.00181, "text": "12"},
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.68,
                "cost": 0.006473,
                "text": "210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 3.55,
                "cost": 0.001956,
                "text": "97.2",
            },
            "q07": {"got": 46.0, "correct": True, "seconds": 2.62, "cost": 0.002108, "text": "46"},
            "q08": {"got": 48.0, "correct": True, "seconds": 2.5, "cost": 0.001854, "text": "48"},
            "q09": {"got": 2.0, "correct": True, "seconds": 2.61, "cost": 0.001778, "text": "2"},
            "q10": {"got": 20.0, "correct": True, "seconds": 3.01, "cost": 0.001542, "text": "20"},
            "q11": {"got": 60.0, "correct": True, "seconds": 3.08, "cost": 0.001455, "text": "60"},
            "q12": {"got": 7.5, "correct": True, "seconds": 3.22, "cost": 0.001053, "text": "7.5"},
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 2.99,
                "cost": 0.002856,
                "text": "68,346,304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 4.02,
                "cost": 0.007072,
                "text": "3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 6.04,
                "cost": 0.010311,
                "text": "653",
            },
            "q16": {"got": 11.0, "correct": True, "seconds": 3.22, "cost": 0.002892, "text": "11"},
            "q17": {"got": 76.0, "correct": True, "seconds": 3.7, "cost": 0.002741, "text": "76"},
            "q18": {"got": 173.0, "correct": True, "seconds": 3.0, "cost": 0.001438, "text": "173"},
            "q19": {"got": 2.0, "correct": True, "seconds": 4.53, "cost": 0.002684, "text": "2"},
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 3.98,
                "cost": 0.002862,
                "text": "401",
            },
        },
    },
    {
        "key": "b02cldn",
        "model": "claude-sonnet-5",
        "style": "direct",
        "context": "noisy",
        "ago": 3.19,
        "seconds": 27.8,
        "by": "Theo Abara",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 3.28,
                "cost": 0.001595,
                "text": "1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.19,
                "cost": 0.006441,
                "text": "210",
            },
            "q03": {"got": 13.0, "correct": True, "seconds": 3.64, "cost": 0.001539, "text": "13"},
            "q04": {"got": 12.0, "correct": True, "seconds": 3.76, "cost": 0.000855, "text": "12"},
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.84,
                "cost": 0.001057,
                "text": "210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 2.54,
                "cost": 0.001849,
                "text": "97.2",
            },
            "q07": {"got": 46.0, "correct": True, "seconds": 3.52, "cost": 0.002125, "text": "46"},
            "q08": {"got": 48.0, "correct": True, "seconds": 3.54, "cost": 0.001928, "text": "48"},
            "q09": {"got": 2.0, "correct": True, "seconds": 2.44, "cost": 0.001802, "text": "2"},
            "q10": {"got": 20.0, "correct": True, "seconds": 3.26, "cost": 0.001543, "text": "20"},
            "q11": {"got": 60.0, "correct": True, "seconds": 4.44, "cost": 0.002783, "text": "60"},
            "q12": {"got": 7.5, "correct": True, "seconds": 3.31, "cost": 0.001587, "text": "7.5"},
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 2.8,
                "cost": 0.002072,
                "text": "68,346,304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 3.35,
                "cost": 0.001823,
                "text": "3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 8.75,
                "cost": 0.012793,
                "text": "653",
            },
            "q16": {"got": 10.0, "correct": False, "seconds": 4.01, "cost": 0.002999, "text": "10"},
            "q17": {"got": 76.0, "correct": True, "seconds": 3.75, "cost": 0.007774, "text": "76"},
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 3.02,
                "cost": 0.001461,
                "text": "173",
            },
            "q19": {"got": 2.0, "correct": True, "seconds": 3.73, "cost": 0.002321, "text": "2"},
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 5.11,
                "cost": 0.008583,
                "text": "401",
            },
        },
    },
    {
        "key": "b03clsc",
        "model": "claude-sonnet-5",
        "style": "steps",
        "context": "clean",
        "ago": 3.18,
        "seconds": 33.9,
        "by": "Theo Abara",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 3.78,
                "cost": 0.002553,
                "text": "17 boxes × 36 books = 612 books bought.\n"
                "1248 + 612 = 1860 books.\n"
                "1860 - 389 = 1471 books.\n"
                "\n"
                "Answer: 1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 2.83,
                "cost": 0.002626,
                "text": "Time = distance/speed = 287/82 = 3.5 hours = 3.5 × 60 = 210 "
                "minutes.\n"
                "\n"
                "Answer: 210",
            },
            "q03": {
                "got": 13.0,
                "correct": True,
                "seconds": 4.16,
                "cost": 0.002795,
                "text": "3,750 ÷ 12 = 312 full cartons (remainder 6 eggs, unused).\n"
                "312 ÷ 24 = 13 full crates exactly.\n"
                "\n"
                "Answer: 13",
            },
            "q04": {
                "got": 12.0,
                "correct": True,
                "seconds": 4.8,
                "cost": 0.007812,
                "text": "Current volume = 3/8 × 2400 = 900 L. Remaining to fill = 2400 − 900 "
                "= 1500 L. Time = 1500 ÷ 125 = 12 hours.\n"
                "\n"
                "Answer: 12",
            },
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 5.56,
                "cost": 0.007189,
                "text": "Marked up price: 240 × 1.25 = $300\n"
                "Sale price: 300 × 0.70 = $210\n"
                "\n"
                "Answer: 210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 3.27,
                "cost": 0.002733,
                "text": "Food + drinks = 186 + 57 = $243\n"
                "Tip = 20% × 243 = $48.60\n"
                "Total = 243 + 48.60 = $291.60\n"
                "Each person pays = 291.60 / 3 = $97.20\n"
                "\n"
                "Answer: 97.2",
            },
            "q07": {
                "got": 46.0,
                "correct": True,
                "seconds": 4.4,
                "cost": 0.003255,
                "text": "Printing time: (504+798+378)/42 = 1680/42 = 40 minutes\n"
                "Warm-up: 2 minutes × 3 documents = 6 minutes\n"
                "Total = 40 + 6 = 46 minutes\n"
                "\n"
                "Answer: 46",
            },
            "q08": {
                "got": 48.0,
                "correct": True,
                "seconds": 4.71,
                "cost": 0.003158,
                "text": "Let daughter's current age = x, Ravi's = 4x.\n"
                "\n"
                "In 6 years: 4x + 6 = 3(x + 6)\n"
                "4x + 6 = 3x + 18\n"
                "x = 12\n"
                "\n"
                "Ravi's age now = 4 × 12 = 48\n"
                "\n"
                "Answer: 48",
            },
            "q09": {
                "got": 2.0,
                "correct": True,
                "seconds": 3.22,
                "cost": 0.003108,
                "text": "Flour per person: 450 g ÷ 6 = 75 g\n"
                "For 22 people: 75 g × 22 = 1650 g = 1.65 kg\n"
                "Since bags are 1 kg each, she needs 2 bags (2 kg covers 1.65 kg "
                "needed).\n"
                "\n"
                "Answer: 2",
            },
            "q10": {
                "got": 20.0,
                "correct": True,
                "seconds": 5.06,
                "cost": 0.007579,
                "text": "Time for first leg: 30/15 = 2 h. Time for second leg: 30/30 = 1 h. "
                "Total distance = 60 km, total time = 3 h. Average speed = 60/3 = 20 "
                "km/h.\n"
                "\n"
                "Answer: 20",
            },
            "q11": {
                "got": 60.0,
                "correct": True,
                "seconds": 5.14,
                "cost": 0.004079,
                "text": "Units digit 7: 7,17,...,297 → 30 occurrences.\n"
                "Tens digit 7: 70-79, 170-179, 270-279 → 3×10 = 30 occurrences.\n"
                "Hundreds digit 7: none (would be 700-799, out of range).\n"
                "\n"
                "Total = 30 + 30 = 60\n"
                "\n"
                "Answer: 60",
            },
            "q12": {
                "got": 7.5,
                "correct": True,
                "seconds": 3.03,
                "cost": 0.002844,
                "text": "At 3:15, minute hand is at 90°, hour hand is at 3*30 + 15*0.5 = "
                "97.5°. Difference = 7.5°.\n"
                "\n"
                "Answer: 7.5",
            },
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 4.02,
                "cost": 0.004033,
                "text": "7384 × 9256:\n"
                "- 7384 × 9000 = 66,456,000\n"
                "- 7384 × 256 = 7384×200 + 7384×56 = 1,476,800 + 413,504 = "
                "1,890,304\n"
                "- Total = 66,456,000 + 1,890,304 = 68,346,304\n"
                "\n"
                "Answer: 68346304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 4.13,
                "cost": 0.003107,
                "text": "Sheets per day = 347 × 829 = 287,663\n"
                "Total = 287,663 × 13 = 3,739,619\n"
                "\n"
                "Answer: 3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 13.48,
                "cost": 0.017948,
                "text": "Counting the days strictly between the two dates (excluding both "
                "endpoints):\n"
                "\n"
                "- Feb 3, 2025 is day 34 of 2025 (non-leap); Dec 31, 2025 is day 365 "
                "→ 331 days from Feb 3, 2025 to Dec 31, 2025.\n"
                "- Nov 19, 2026 is day 323 of 2026 (non-leap).\n"
                "- Total gap (date2 − date1) = 331 + 323 = 654 days.\n"
                "- Days strictly between = 654 − 1 = 653.\n"
                "\n"
                "Answer: 653",
            },
            "q16": {
                "got": 11.0,
                "correct": True,
                "seconds": 4.0,
                "cost": 0.004269,
                "text": 'Counting "e" in each word:\n'
                "- nevertheless: 4\n"
                "- the: 1\n"
                "- seventeen: 4\n"
                "- elephants: 2\n"
                "\n"
                "Total: 4+1+4+2 = 11\n"
                "\n"
                "Answer: 11",
            },
            "q17": {
                "got": 76.0,
                "correct": True,
                "seconds": 4.26,
                "cost": 0.00841,
                "text": "2^50 = 1,125,899,906,842,624\n"
                "\n"
                "Sum of digits: 1+1+2+5+8+9+9+9+0+6+8+4+2+6+2+4 = 76\n"
                "\n"
                "Answer: 76",
            },
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 5.47,
                "cost": 0.005542,
                "text": "Listing primes in order: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29 (10th), "
                "31, 37, 41, 43, 47, 53, 59, 61, 67, 71 (20th), 73, 79, 83, 89, 97, "
                "101, 103, 107, 109, 113 (30th), 127, 131, 137, 139, 149, 151, 157, "
                "163, 167, 173 (40th).\n"
                "\n"
                "Answer: 173",
            },
            "q19": {
                "got": 2.0,
                "correct": True,
                "seconds": 4.36,
                "cost": 0.008217,
                "text": "7^10 ≡ 1 (mod 11) by Fermat's little theorem.\n"
                "123 = 12×10 + 3, so 7^123 ≡ 7^3 (mod 11).\n"
                "7^3 = 343 = 31×11 + 2.\n"
                "\n"
                "Answer: 2",
            },
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 4.79,
                "cost": 0.004985,
                "text": "Divisible by 3 or 5: floor(1000/3)+floor(1000/5)-floor(1000/15) = "
                "333+200-66 = 467\n"
                "\n"
                "Among these, divisible by 7 (i.e., by 21 or 35): "
                "floor(1000/21)+floor(1000/35)-floor(1000/105) = 47+28-9 = 66\n"
                "\n"
                "Subtract: 467 - 66 = 401\n"
                "\n"
                "Answer: 401",
            },
        },
    },
    {
        "key": "b04clsn",
        "model": "claude-sonnet-5",
        "style": "steps",
        "context": "noisy",
        "ago": 3.17,
        "seconds": 32.6,
        "by": "Theo Abara",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 4.32,
                "cost": 0.003394,
                "text": "Library starts with 1,248 books.\n"
                "\n"
                "Books bought: 17 × 36 = 612\n"
                "Total after buying: 1,248 + 612 = 1,860\n"
                "After giving 389 to the school: 1,860 − 389 = 1,471\n"
                "\n"
                "(The distance to the school and number of classrooms are irrelevant "
                "to the book count.)\n"
                "\n"
                "Answer: 1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 4.19,
                "cost": 0.002878,
                "text": "Time = distance / speed = 287 km ÷ 82 km/h = 3.5 hours = 210 "
                "minutes.\n"
                "\n"
                "(The carriages/seating info isn't needed for this calculation.)\n"
                "\n"
                "Answer: 210",
            },
            "q03": {
                "got": 13.0,
                "correct": True,
                "seconds": 5.75,
                "cost": 0.008139,
                "text": "3,750 eggs ÷ 12 = 312 full cartons (with 6 eggs left over, "
                "discarded as not full).\n"
                "312 cartons ÷ 24 = 13 full crates exactly.\n"
                "\n"
                "(Hens/roosters count is irrelevant to the egg packing "
                "calculation.)\n"
                "\n"
                "Answer: 13",
            },
            "q04": {
                "got": 12.0,
                "correct": True,
                "seconds": 4.31,
                "cost": 0.002785,
                "text": "Current volume: 3/8 × 2400 = 900 litres.\n"
                "Remaining to fill: 2400 − 900 = 1500 litres.\n"
                "Time: 1500 ÷ 125 = 12 hours.\n"
                "\n"
                "(The paint color and empty weight are irrelevant to the "
                "calculation.)\n"
                "\n"
                "Answer: 12",
            },
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 4.21,
                "cost": 0.003083,
                "text": "Marked-up price: $240 × 1.25 = $300\n"
                "Sale price: $300 × (1 − 0.30) = $300 × 0.70 = $210\n"
                "\n"
                "(The 1,150 jackets sold figure doesn't affect the per-jacket sale "
                "price.)\n"
                "\n"
                "Answer: 210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 4.38,
                "cost": 0.003232,
                "text": "Food + drinks = 186 + 57 = $243\n"
                "Tip = 20% × 243 = $48.60\n"
                "Total = 243 + 48.60 = $291.60\n"
                "Split three ways = 291.60 / 3 = $97.20 each\n"
                "\n"
                "(The 6 km walk detail doesn't affect the bill split.)\n"
                "\n"
                "Answer: 97.20",
            },
            "q07": {
                "got": 46.0,
                "correct": True,
                "seconds": 4.97,
                "cost": 0.003741,
                "text": "Printing time: (504+798+378)/42 = 1680/42 = 40 minutes.\n"
                "Warm-up: 2 minutes × 3 documents = 6 minutes.\n"
                "Total = 40 + 6 = 46 minutes.\n"
                "\n"
                "(The printer's price and number of paper trays are irrelevant to "
                "the timing.)\n"
                "\n"
                "Answer: 46",
            },
            "q08": {
                "got": 48.0,
                "correct": True,
                "seconds": 4.31,
                "cost": 0.003536,
                "text": "Let daughter's age = x, so Ravi = 4x.\n"
                "\n"
                "In 6 years: 4x + 6 = 3(x + 6)\n"
                "4x + 6 = 3x + 18\n"
                "x = 12\n"
                "\n"
                "Ravi now = 4 × 12 = 48\n"
                "\n"
                "(Ravi's father's age of 79 is extra information not needed for this "
                "calculation.)\n"
                "\n"
                "Answer: 48",
            },
            "q09": {
                "got": 2.0,
                "correct": True,
                "seconds": 4.46,
                "cost": 0.008673,
                "text": "Flour per person: 450 g ÷ 6 = 75 g\n"
                "For 22 people: 75 × 22 = 1650 g = 1.65 kg\n"
                "Bags come in 1 kg units, so she must round up: 2 bags.\n"
                "\n"
                "(The 3 kg of sugar for $4 is irrelevant to the flour question.)\n"
                "\n"
                "Answer: 2",
            },
            "q10": {
                "got": 20.0,
                "correct": True,
                "seconds": 3.95,
                "cost": 0.003067,
                "text": "Time for first leg: 30/15 = 2 h\n"
                "Time for second leg: 30/30 = 1 h\n"
                "Total distance = 60 km, total time = 3 h\n"
                "Average speed = 60/3 = 20 km/h\n"
                "\n"
                "(Bike weight and gear count are irrelevant to the calculation.)\n"
                "\n"
                "Answer: 20",
            },
            "q11": {
                "got": 60.0,
                "correct": True,
                "seconds": 4.64,
                "cost": 0.004357,
                "text": "Counting digit 7 occurrences from 1 to 300:\n"
                "\n"
                "- Units place: 7, 17, 27, ..., 297 → 30 occurrences\n"
                "- Tens place: 70–79, 170–179, 270–279 → 3×10 = 30 occurrences\n"
                "- Hundreds place: none (no 700s in range) → 0\n"
                "\n"
                "Total = 30 + 30 + 0 = 60\n"
                "\n"
                "Answer: 60",
            },
            "q12": {
                "got": 7.5,
                "correct": True,
                "seconds": 3.36,
                "cost": 0.003114,
                "text": "Minute hand at 3:15 is at 90° (15 min × 6°/min).\n"
                "Hour hand is at 3×30 + 15×0.5 = 90 + 7.5 = 97.5°.\n"
                "Difference = 97.5 − 90 = 7.5°.\n"
                "\n"
                "Answer: 7.5",
            },
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 4.37,
                "cost": 0.003359,
                "text": "7,384 × 9,256 = 68,346,304 (the year opened and number of loading "
                "bays are irrelevant to the total screw count).\n"
                "\n"
                "Answer: 68346304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 4.64,
                "cost": 0.007657,
                "text": "Total sheets = 347 jobs/day × 829 sheets/job × 13 days\n"
                "347 × 829 = 287,663\n"
                "287,663 × 13 = 3,739,619\n"
                "\n"
                "Answer: 3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 9.13,
                "cost": 0.00988,
                "text": "Days from Feb 3, 2025 to Feb 3, 2026 = 365 (no leap day in "
                "between).\n"
                "Days from Feb 3, 2026 to Nov 19, 2026 = 289 (day-of-year 323 minus "
                "34).\n"
                "\n"
                "Total days between the two dates (inclusive counting as a span) = "
                "365 + 289 = 654.\n"
                "\n"
                "Strictly between (excluding both endpoints) = 654 − 1 = 653.\n"
                "\n"
                "Answer: 653",
            },
            "q16": {
                "got": 11.0,
                "correct": True,
                "seconds": 4.86,
                "cost": 0.004251,
                "text": 'Counting "e" in each word:\n'
                "- nevertheless → 4\n"
                "- the → 1\n"
                "- seventeen → 4\n"
                "- elephants → 2\n"
                "\n"
                "Total: 4+1+4+2 = 11\n"
                "\n"
                "Answer: 11",
            },
            "q17": {
                "got": 76.0,
                "correct": True,
                "seconds": 4.31,
                "cost": 0.008557,
                "text": "2^50 = 1,125,899,906,842,624\n"
                "\n"
                "Sum of digits: 1+1+2+5+8+9+9+9+0+6+8+4+2+6+2+4 = 76\n"
                "\n"
                "Answer: 76",
            },
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 5.88,
                "cost": 0.009142,
                "text": "The 40th prime number is 173.\n\nAnswer: 173",
            },
            "q19": {
                "got": 2.0,
                "correct": True,
                "seconds": 3.87,
                "cost": 0.003745,
                "text": "By Fermat's Little Theorem, since 11 is prime: 7^10 ≡ 1 (mod 11).\n"
                "\n"
                "123 = 12×10 + 3, so 7^123 ≡ 7^3 (mod 11).\n"
                "\n"
                "7^2 = 49 ≡ 5 (mod 11)\n"
                "7^3 = 7×5 = 35 ≡ 2 (mod 11)\n"
                "\n"
                "Answer: 2",
            },
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 5.37,
                "cost": 0.005177,
                "text": "Count divisible by 3 or 5 (1–1000): "
                "floor(1000/3)+floor(1000/5)-floor(1000/15) = 333+200-66 = 467.\n"
                "\n"
                "Now subtract those also divisible by 7, i.e., divisible by 21 or "
                "35:\n"
                "floor(1000/21)=47, floor(1000/35)=28, floor(1000/105)=9\n"
                "47+28-9 = 66.\n"
                "\n"
                "467 - 66 = 401.\n"
                "\n"
                "Answer: 401",
            },
        },
    },
    {
        "key": "b05hadc",
        "model": "haiku",
        "style": "direct",
        "context": "clean",
        "ago": 2.06,
        "seconds": 25.5,
        "by": "Ines Varga",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 3.18,
                "cost": 0.000491,
                "text": "1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 2.35,
                "cost": 0.000166,
                "text": "210",
            },
            "q03": {"got": 13.0, "correct": True, "seconds": 3.31, "cost": 0.00022, "text": "13"},
            "q04": {"got": 12.0, "correct": True, "seconds": 2.99, "cost": 0.000197, "text": "12"},
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.06,
                "cost": 0.000538,
                "text": "210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 2.49,
                "cost": 0.000213,
                "text": "97.2",
            },
            "q07": {"got": 46.0, "correct": True, "seconds": 2.4, "cost": 3.7e-05, "text": "46"},
            "q08": {"got": 48.0, "correct": True, "seconds": 5.99, "cost": 0.000198, "text": "48"},
            "q09": {"got": 2.0, "correct": True, "seconds": 3.02, "cost": 0.000339, "text": "2"},
            "q10": {"got": 20.0, "correct": True, "seconds": 3.37, "cost": 0.000207, "text": "20"},
            "q11": {"got": 60.0, "correct": True, "seconds": 3.36, "cost": 6.6e-05, "text": "60"},
            "q12": {"got": 7.5, "correct": True, "seconds": 3.71, "cost": 0.0005, "text": "7.5"},
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 3.38,
                "cost": 0.000557,
                "text": "68346304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 4.24,
                "cost": 0.000581,
                "text": "3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 4.44,
                "cost": 0.000508,
                "text": "653",
            },
            "q16": {"got": 12.0, "correct": False, "seconds": 3.71, "cost": 0.000413, "text": "12"},
            "q17": {"got": 76.0, "correct": True, "seconds": 3.85, "cost": 0.000535, "text": "76"},
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 3.69,
                "cost": 0.000354,
                "text": "173",
            },
            "q19": {"got": 2.0, "correct": True, "seconds": 2.26, "cost": 0.000289, "text": "2"},
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 4.74,
                "cost": 0.000564,
                "text": "401",
            },
        },
    },
    {
        "key": "b06hadn",
        "model": "haiku",
        "style": "direct",
        "context": "noisy",
        "ago": 2.05,
        "seconds": 23.9,
        "by": "Ines Varga",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 2.93,
                "cost": 0.00021,
                "text": "1471",
            },
            "q02": {"got": 210.0, "correct": True, "seconds": 3.1, "cost": 0.000463, "text": "210"},
            "q03": {"got": 13.0, "correct": True, "seconds": 2.36, "cost": 4.5e-05, "text": "13"},
            "q04": {"got": 12.0, "correct": True, "seconds": 2.42, "cost": 3.7e-05, "text": "12"},
            "q05": {"got": 210.0, "correct": True, "seconds": 3.0, "cost": 0.000339, "text": "210"},
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 3.68,
                "cost": 0.000222,
                "text": "97.2",
            },
            "q07": {"got": 46.0, "correct": True, "seconds": 3.0, "cost": 0.000259, "text": "46"},
            "q08": {"got": 48.0, "correct": True, "seconds": 2.35, "cost": 0.000174, "text": "48"},
            "q09": {"got": 2.0, "correct": True, "seconds": 2.67, "cost": 0.00022, "text": "2"},
            "q10": {"got": 20.0, "correct": True, "seconds": 2.77, "cost": 0.000159, "text": "20"},
            "q11": {"got": 60.0, "correct": True, "seconds": 3.81, "cost": 0.000661, "text": "60"},
            "q12": {"got": 7.5, "correct": True, "seconds": 3.26, "cost": 0.000278, "text": "7.5"},
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 2.97,
                "cost": 0.000431,
                "text": "68,346,304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 3.1,
                "cost": 0.000167,
                "text": "3739619",
            },
            "q15": {"got": 653.0, "correct": True, "seconds": 3.75, "cost": 0.00047, "text": "653"},
            "q16": {"got": 11.0, "correct": True, "seconds": 3.09, "cost": 0.000207, "text": "11"},
            "q17": {"got": 76.0, "correct": True, "seconds": 3.13, "cost": 0.000323, "text": "76"},
            "q18": {"got": 173.0, "correct": True, "seconds": 2.61, "cost": 0.00033, "text": "173"},
            "q19": {"got": 2.0, "correct": True, "seconds": 2.3, "cost": 0.000155, "text": "2"},
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 5.54,
                "cost": 0.000457,
                "text": "401",
            },
        },
    },
    {
        "key": "b07hasc",
        "model": "haiku",
        "style": "steps",
        "context": "clean",
        "ago": 2.04,
        "seconds": 26.0,
        "by": "Ines Varga",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 2.35,
                "cost": 6.2e-05,
                "text": "Boxes add 17 × 36 = 612 books. The library then has 1,248 + 612 = "
                "1,860 books. After giving away 389, it has 1,860 − 389 = 1,471 "
                "books.\n"
                "\n"
                "Answer: 1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.62,
                "cost": 0.000234,
                "text": "The trip takes 3.5 hours at 82 km/h, since 287 ÷ 82 = 3.5 hours. "
                "Converting to minutes: 3.5 × 60 = 210 minutes.\n"
                "\n"
                "Answer: 210",
            },
            "q03": {
                "got": 13.0,
                "correct": True,
                "seconds": 3.83,
                "cost": 0.000313,
                "text": "Each carton holds 12 eggs, so 3,750 ÷ 12 = 312 full cartons, with 6 "
                "eggs left over.\n"
                "\n"
                "Each crate holds 24 cartons, so 312 ÷ 24 = 13 full crates, with no "
                "cartons left over.\n"
                "\n"
                "Answer: 13",
            },
            "q04": {
                "got": 12.0,
                "correct": True,
                "seconds": 3.32,
                "cost": 0.000297,
                "text": "The tank currently holds 3/8 × 2,400 = 900 litres.\n"
                "\n"
                "It needs 2,400 − 900 = 1,500 more litres.\n"
                "\n"
                "At 125 litres per hour, that takes 1,500 ÷ 125 = 12 hours.\n"
                "\n"
                "Answer: 12",
            },
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.63,
                "cost": 0.000232,
                "text": "The jacket is marked up 25% from $240: $240 × 1.25 = $300.\n"
                "\n"
                "The sale price is 30% off $300: $300 × 0.70 = $210.\n"
                "\n"
                "Answer: 210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 3.03,
                "cost": 0.000258,
                "text": "Subtotal: $186 + $57 = $243\n"
                "Tip: 20% of $243 = $48.60\n"
                "Total: $243 + $48.60 = $291.60\n"
                "Per person: $291.60 ÷ 3 = $97.20\n"
                "\n"
                "Answer: 97.20",
            },
            "q07": {
                "got": 46.0,
                "correct": True,
                "seconds": 3.17,
                "cost": 0.000356,
                "text": "Total pages: 504 + 798 + 378 = 1,680.\n"
                "\n"
                "Printing time: 1,680 ÷ 42 = 40 minutes (504 ÷ 42 = 12, 798 ÷ 42 = "
                "19, 378 ÷ 42 = 9).\n"
                "\n"
                "Warm-up: 3 documents × 2 minutes = 6 minutes.\n"
                "\n"
                "Total: 40 + 6 = 46 minutes.\n"
                "\n"
                "Answer: 46",
            },
            "q08": {
                "got": 48.0,
                "correct": True,
                "seconds": 3.87,
                "cost": 0.000576,
                "text": "Let the daughter's age now be d. Ravi's age now is 4d.\n"
                "\n"
                "In 6 years, Ravi will be 4d + 6 and the daughter will be d + 6. The "
                "condition gives:\n"
                "\n"
                "4d + 6 = 3(d + 6)\n"
                "4d + 6 = 3d + 18\n"
                "d = 12\n"
                "\n"
                "So the daughter is 12 and Ravi is 4 × 12 = 48.\n"
                "\n"
                "Check: in 6 years Ravi is 54 and his daughter is 18, and 54 = 3 × "
                "18.\n"
                "\n"
                "Answer: 48",
            },
            "q09": {
                "got": 2.0,
                "correct": True,
                "seconds": 3.58,
                "cost": 0.000311,
                "text": "For 22 people, the recipe needs 22 ÷ 6 = 11/3 times the original "
                "amount.\n"
                "\n"
                "450 g × 11/3 = 1650 g = 1.65 kg\n"
                "\n"
                "Since bags are 1 kg each, 1.65 kg needs 2 bags (1 bag is not "
                "enough, and 2 bags give 2 kg).\n"
                "\n"
                "Answer: 2",
            },
            "q10": {
                "got": 20.0,
                "correct": True,
                "seconds": 4.19,
                "cost": 0.000578,
                "text": "**Step 1: Time for each leg**\n"
                "- First leg: 30 km ÷ 15 km/h = 2 hours\n"
                "- Second leg: 30 km ÷ 30 km/h = 1 hour\n"
                "\n"
                "**Step 2: Totals**\n"
                "- Total distance: 30 + 30 = 60 km\n"
                "- Total time: 2 + 1 = 3 hours\n"
                "\n"
                "**Step 3: Average speed**\n"
                "- Average speed = total distance ÷ total time = 60 km ÷ 3 h = 20 "
                "km/h\n"
                "\n"
                "Note that this is not the simple average of 15 and 30 (which would "
                "be 22.5 km/h), because she spends more time on the slower leg.\n"
                "\n"
                "Answer: 20",
            },
            "q11": {
                "got": 60.0,
                "correct": True,
                "seconds": 3.81,
                "cost": 0.000444,
                "text": "Count the 7s by place value, using the numbers 1 to 300.\n"
                "\n"
                "- **Units digit is 7:** 7, 17, 27, ..., 297. That is 30 numbers "
                "(one per block of ten, across 30 blocks).\n"
                "- **Tens digit is 7:** 70–79, 170–179, 270–279. That is 30 "
                "numbers.\n"
                "- **Hundreds digit is 7:** None, since the hundreds digits in this "
                "range are only 1, 2, and 3.\n"
                "\n"
                "Total: 30 + 30 = 60.\n"
                "\n"
                "Answer: 60",
            },
            "q12": {
                "got": 7.5,
                "correct": True,
                "seconds": 4.07,
                "cost": 0.000444,
                "text": "At 3:15, the minute hand points to 3 (90°). The hour hand has moved "
                "3 × 30° = 90° plus 15/60 of the way to the next hour, which is 0.25 "
                "× 30° = 7.5°, so it sits at 97.5°.\n"
                "\n"
                "The difference is 97.5° − 90° = 7.5°, which is already less than "
                "180°, so it is the smaller angle.\n"
                "\n"
                "Answer: 7.5",
            },
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 3.49,
                "cost": 0.000471,
                "text": "Multiply the number of shelves by the screws per shelf:\n"
                "\n"
                "7,384 × 9,256 = 7,384 × 9,000 + 7,384 × 256\n"
                "= 66,456,000 + 1,890,304\n"
                "= 68,346,304\n"
                "\n"
                "Answer: 68346304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 3.72,
                "cost": 0.000426,
                "text": "Sheets per day: 347 jobs × 829 sheets = 287,663 sheets.\n"
                "\n"
                "Over 13 days: 287,663 × 13 = 3,739,619 sheets.\n"
                "\n"
                "Answer: 3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 5.75,
                "cost": 0.000524,
                "text": "Count the days from 3 February 2025 to 19 November 2026.\n"
                "\n"
                "- **Day of year for 3 Feb 2025:** 31 + 3 = day 34 of 2025.\n"
                "- **Days remaining in 2025 after that date:** 365 − 34 = 331.\n"
                "- **Day of year for 19 Nov 2026** (2026 is not a leap year): 31 + "
                "28 + 31 + 30 + 31 + 30 + 31 + 31 + 30 + 31 + 19 = 323.\n"
                "- **Total difference:** 331 + 323 = 654 days.\n"
                "\n"
                "Since the endpoints are excluded, subtract 1 from 654.\n"
                "\n"
                "Answer: 653",
            },
            "q16": {
                "got": 11.0,
                "correct": True,
                "seconds": 4.54,
                "cost": 0.000683,
                "text": "Counting the letter e in each word:\n"
                "\n"
                "- **nevertheless**: n-**e**-v-**e**-r-t-h-**e**-l-**e**-s-s → 4\n"
                "- **the**: t-h-**e** → 1\n"
                "- **seventeen**: s-**e**-v-**e**-n-t-**e**-**e**-n → 4\n"
                "- **elephants**: **e**-l-**e**-p-h-a-n-t-s → 2\n"
                "\n"
                "Total: 4 + 1 + 4 + 2 = 11\n"
                "\n"
                "Answer: 11",
            },
            "q17": {
                "got": 76.0,
                "correct": True,
                "seconds": 2.93,
                "cost": 0.000353,
                "text": "2^50 = 1,125,899,906,842,624.\n"
                "\n"
                "Adding its digits: 1+1+2+5+8+9+9+9+0+6+8+4+2+6+2+4 = 76.\n"
                "\n"
                "Answer: 76",
            },
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 3.47,
                "cost": 0.000442,
                "text": "The primes in order are counted in groups of ten:\n"
                "\n"
                "1. 2, 3, 5, 7, 11, 13, 17, 19, 23, 29 (1st to 10th)\n"
                "2. 31, 37, 41, 43, 47, 53, 59, 61, 67, 71 (11th to 20th)\n"
                "3. 73, 79, 83, 89, 97, 101, 103, 107, 109, 113 (21st to 30th)\n"
                "4. 127, 131, 137, 139, 149, 151, 157, 163, 167, 173 (31st to 40th)\n"
                "\n"
                "Answer: 173",
            },
            "q19": {
                "got": 2.0,
                "correct": True,
                "seconds": 3.0,
                "cost": 0.000385,
                "text": "Since 11 is prime, Fermat's Little Theorem gives 7^10 ≡ 1 (mod "
                "11).\n"
                "\n"
                "1. Reduce the exponent: 123 = 12·10 + 3, so 7^123 ≡ 7^3 (mod 11).\n"
                "2. Compute 7^3 = 343.\n"
                "3. Divide: 343 = 11·31 + 2, so 343 ≡ 2 (mod 11).\n"
                "\n"
                "The remainder is 2.\n"
                "\n"
                "Answer: 2",
            },
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 4.85,
                "cost": 0.000694,
                "text": "Count the numbers from 1 to 1000 divisible by 3 or 5, then subtract "
                "those also divisible by 7.\n"
                "\n"
                "1. **Divisible by 3 or 5:** By inclusion-exclusion, 333 (multiples "
                "of 3) + 200 (multiples of 5) − 66 (multiples of 15) = 467.\n"
                "\n"
                "2. **Divisible by 3 or 5 and also by 7:** These are multiples of 21 "
                "or 35. Multiples of 21 are 47, multiples of 35 are 28, and "
                "multiples of 105 are 9. So 47 + 28 − 9 = 66.\n"
                "\n"
                "3. **Subtract:** 467 − 66 = 401.\n"
                "\n"
                "Answer: 401",
            },
        },
    },
    {
        "key": "b08hasn",
        "model": "haiku",
        "style": "steps",
        "context": "noisy",
        "ago": 2.03,
        "seconds": 31.6,
        "by": "Ines Varga",
        "answers": {
            "q01": {
                "got": 1471.0,
                "correct": True,
                "seconds": 4.2,
                "cost": 0.000573,
                "text": "The distance (14 km) and classroom count (27) don't affect the book "
                "count, so I'll ignore them.\n"
                "\n"
                "1. Books bought: 17 × 36 = 612\n"
                "2. Books after purchase: 1,248 + 612 = 1,860\n"
                "3. Books after giving to the school: 1,860 − 389 = 1,471\n"
                "\n"
                "Answer: 1471",
            },
            "q02": {
                "got": 210.0,
                "correct": True,
                "seconds": 3.35,
                "cost": 0.00033,
                "text": "The trip time depends only on distance and speed. The carriage and "
                "seating details don't affect it.\n"
                "\n"
                "1. Time = distance ÷ speed = 287 km ÷ 82 km/h = 3.5 hours.\n"
                "2. Convert to minutes: 3.5 × 60 = 210 minutes.\n"
                "\n"
                "Answer: 210",
            },
            "q03": {
                "got": 13.0,
                "correct": True,
                "seconds": 3.19,
                "cost": 0.000252,
                "text": "**Step 1: Full cartons.** 3,750 ÷ 12 = 312 remainder 6, so 312 full "
                "cartons. The 6 leftover eggs don't fill a carton.\n"
                "\n"
                "**Step 2: Full crates.** 312 ÷ 24 = 13 exactly, so 13 full crates.\n"
                "\n"
                "The hens and roosters don't affect the count.\n"
                "\n"
                "Answer: 13",
            },
            "q04": {
                "got": 12.0,
                "correct": True,
                "seconds": 3.89,
                "cost": 0.00035,
                "text": "The tank holds 2,400 litres and is 3/8 full, so it currently has "
                "2,400 × 3/8 = 900 litres.\n"
                "\n"
                "To fill it, it needs 2,400 − 900 = 1,500 more litres.\n"
                "\n"
                "At 125 litres an hour, that takes 1,500 ÷ 125 = 12 hours.\n"
                "\n"
                "The paint year and the tank's empty weight don't affect the fill "
                "time.\n"
                "\n"
                "Answer: 12",
            },
            "q05": {
                "got": 210.0,
                "correct": True,
                "seconds": 4.32,
                "cost": 0.000566,
                "text": "The jacket's marked-up price is $240 × 1.25 = $300.\n"
                "\n"
                "The sale price is 30% off $300: $300 × 0.70 = $210.\n"
                "\n"
                "The 1,150 jackets sold last year doesn't affect the price.\n"
                "\n"
                "Answer: 210",
            },
            "q06": {
                "got": 97.2,
                "correct": True,
                "seconds": 4.36,
                "cost": 0.000319,
                "text": "The 6 km walk doesn't affect the bill, so I'll ignore it.\n"
                "\n"
                "1. Subtotal: $186 + $57 = $243\n"
                "2. Tip: 20% of $243 = $48.60\n"
                "3. Total: $243 + $48.60 = $291.60\n"
                "4. Per person: $291.60 ÷ 3 = $97.20\n"
                "\n"
                "Each friend pays $97.20.\n"
                "\n"
                "Answer: 97.2",
            },
            "q07": {
                "got": 46.0,
                "correct": True,
                "seconds": 2.81,
                "cost": 0.000139,
                "text": "**Step 1: Total pages.** 504 + 798 + 378 = 1,680 pages.\n"
                "\n"
                "**Step 2: Printing time.** 1,680 ÷ 42 = 40 minutes.\n"
                "\n"
                "**Step 3: Warm-up time.** There is a 2-minute warm-up before each "
                "of the 3 documents: 3 × 2 = 6 minutes.\n"
                "\n"
                "**Step 4: Total.** 40 + 6 = 46 minutes. The printer's cost and its "
                "four paper trays don't affect the time.\n"
                "\n"
                "Answer: 46",
            },
            "q08": {
                "got": 48.0,
                "correct": True,
                "seconds": 4.31,
                "cost": 0.000372,
                "text": "Let Ravi's age be R and his daughter's age be D.\n"
                "\n"
                "1. Ravi is 4 times as old as his daughter: R = 4D.\n"
                "2. In 6 years, Ravi is 3 times as old as her: R + 6 = 3(D + 6).\n"
                "3. Substitute R = 4D into the second equation: 4D + 6 = 3D + 18, so "
                "D = 12.\n"
                "4. Then R = 4 × 12 = 48.\n"
                "\n"
                "Ravi's father's age (79) isn't needed to find Ravi's age.\n"
                "\n"
                "Check: in 6 years, Ravi is 54 and his daughter is 18, and 54 = 3 × "
                "18.\n"
                "\n"
                "Answer: 48",
            },
            "q09": {
                "got": 2.0,
                "correct": True,
                "seconds": 3.14,
                "cost": 0.000357,
                "text": "Scale the flour for 22 people: 450 g × (22 ÷ 6) = 450 × 3.667 = "
                "1,650 g = 1.65 kg.\n"
                "\n"
                "Flour comes in 1 kg bags, so she needs 2 bags (2 kg), since one bag "
                "is not enough. The sugar purchase doesn't affect the flour count.\n"
                "\n"
                "Answer: 2",
            },
            "q10": {
                "got": 20.0,
                "correct": True,
                "seconds": 2.77,
                "cost": 0.000254,
                "text": "The average speed is total distance divided by total time, not the "
                "mean of the two speeds.\n"
                "\n"
                "- First leg: 30 km ÷ 15 km/h = 2 h\n"
                "- Second leg: 30 km ÷ 30 km/h = 1 h\n"
                "- Total: 60 km in 3 h\n"
                "\n"
                "The bike's weight and gear count don't affect the calculation.\n"
                "\n"
                "Average speed = 60 km ÷ 3 h = 20 km/h\n"
                "\n"
                "Answer: 20",
            },
            "q11": {
                "got": 60.0,
                "correct": True,
                "seconds": 3.55,
                "cost": 0.000427,
                "text": "Count the 7s by place value.\n"
                "\n"
                "- **Units digit:** Every block of ten has one number ending in 7 "
                "(7, 17, ..., 297). There are 30 such blocks from 1 to 300, so "
                "**30** sevens.\n"
                "- **Tens digit:** The numbers 70–79, 170–179, and 270–279 each have "
                "a tens digit of 7. That gives 3 × 10 = **30** sevens.\n"
                "- **Hundreds digit:** No number from 1 to 300 has a hundreds digit "
                "of 7, so **0** sevens.\n"
                "\n"
                "Total: 30 + 30 + 0 = 60.\n"
                "\n"
                "Answer: 60",
            },
            "q12": {
                "got": 7.5,
                "correct": True,
                "seconds": 9.9,
                "cost": 0.00031,
                "text": "At 3:15, the minute hand points at the 3, which is 90°from the 12. "
                "The hour hand has moved a quarter of the way from the 3 toward the "
                "4, so it's at 90° + 0.5° × 15 = 97.5°.\n"
                "\n"
                "The difference is 97.5° − 90° = 7.5°, which is already the smaller "
                "angle since it's less than 180°.\n"
                "\n"
                "The price and the height on the wall don't affect the angle.\n"
                "\n"
                "Answer: 7.5",
            },
            "q13": {
                "got": 68346304.0,
                "correct": True,
                "seconds": 3.77,
                "cost": 0.000468,
                "text": "The total is shelves × screws per shelf. The year the warehouse "
                "opened and the number of loading bays don't affect the count.\n"
                "\n"
                "1. Multiply: 7,384 × 9,256\n"
                "2. Split 9,256 into 9,000 + 256:\n"
                "   - 7,384 × 9,000 = 66,456,000\n"
                "   - 7,384 × 256 = 1,890,304\n"
                "3. Add: 66,456,000 + 1,890,304 = 68,346,304\n"
                "\n"
                "Answer: 68346304",
            },
            "q14": {
                "got": 3739619.0,
                "correct": True,
                "seconds": 3.46,
                "cost": 0.000484,
                "text": "The printer makes 347 jobs × 829 sheets = 287,663 sheets per day. "
                "Over 13 days, that's 287,663 × 13 = 3,739,619 sheets. The sheet "
                "weight (about 5 grams) doesn't affect the count.\n"
                "\n"
                "Answer: 3739619",
            },
            "q15": {
                "got": 653.0,
                "correct": True,
                "seconds": 6.05,
                "cost": 0.001014,
                "text": "**Step 1: Days from 3 Feb 2025 to 3 Feb 2026.** 2025 is not a leap "
                "year, and February 2026 has no 29th, so this span is 365 days.\n"
                "\n"
                "**Step 2: Days from 3 Feb 2026 to 19 Nov 2026.**\n"
                "- Day of year for 3 Feb 2026: 31 + 3 = 34\n"
                "- Day of year for 19 Nov 2026: 31 + 28 + 31 + 30 + 31 + 30 + 31 + "
                "31 + 30 + 31 + 19 = 323\n"
                "- Difference: 323 − 34 = 289 days\n"
                "\n"
                "**Step 3: Total difference.** 365 + 289 = 654 days from 3 Feb 2025 "
                "to 19 Nov 2026.\n"
                "\n"
                "**Step 4: Strictly between.** Excluding both endpoints removes one "
                "day from the count: 654 − 1 = 653.\n"
                "\n"
                "The weekday information isn't needed for this count.\n"
                "\n"
                "Answer: 653",
            },
            "q16": {
                "got": 11.0,
                "correct": True,
                "seconds": 3.84,
                "cost": 0.000556,
                "text": 'Count the letter "e" in each word:\n'
                "\n"
                "- **nevertheless**: n-**e**-v-**e**-r-t-h-**e**-l-**e**-s-s → 4\n"
                "- **the**: t-h-**e** → 1\n"
                "- **seventeen**: s-**e**-v-**e**-n-t-**e**-**e**-n → 4\n"
                "- **elephants**: **e**-l-**e**-p-h-a-n-t-s → 2\n"
                "\n"
                "Total: 4 + 1 + 4 + 2 = 11\n"
                "\n"
                "Answer: 11",
            },
            "q17": {
                "got": 76.0,
                "correct": True,
                "seconds": 4.71,
                "cost": 0.000658,
                "text": "2^50 = 1,125,899,906,842,624.\n"
                "\n"
                "Its digits are 1, 1, 2, 5, 8, 9, 9, 9, 0, 6, 8, 4, 2, 6, 2, 4.\n"
                "\n"
                "Adding them gives 76.\n"
                "\n"
                "Answer: 76",
            },
            "q18": {
                "got": 173.0,
                "correct": True,
                "seconds": 4.87,
                "cost": 0.000648,
                "text": "The first 25 primes run up to 97, so I count from there:\n"
                "\n"
                "- 101, 103, 107, 109, 113 (26th to 30th)\n"
                "- 127, 131, 137, 139, 149 (31st to 35th)\n"
                "- 151, 157, 163, 167, 173 (36th to 40th)\n"
                "\n"
                "Answer: 173",
            },
            "q19": {
                "got": 2.0,
                "correct": True,
                "seconds": 5.02,
                "cost": 0.000549,
                "text": "Since 11 is prime, Fermat's Little Theorem gives 7^10 ≡ 1 (mod "
                "11).\n"
                "\n"
                "1. Reduce the exponent: 123 = 10·12 + 3, so 7^123 ≡ 7^3 (mod 11).\n"
                "2. Compute 7^3 = 343.\n"
                "3. Divide: 343 = 11·31 + 2, so 343 ≡ 2 (mod 11).\n"
                "\n"
                "Check: 7^2 = 49 ≡ 5 (mod 11), and 5·7 = 35 ≡ 2 (mod 11).\n"
                "\n"
                "The remainder is 2.\n"
                "\n"
                "Answer: 2",
            },
            "q20": {
                "got": 401.0,
                "correct": True,
                "seconds": 4.98,
                "cost": 0.000805,
                "text": "Count the numbers from 1 to 1,000 divisible by 3 or 5, then remove "
                "those also divisible by 7.\n"
                "\n"
                "1. **Divisible by 3 or 5:**\n"
                "   - Divisible by 3: ⌊1000/3⌋ = 333\n"
                "   - Divisible by 5: ⌊1000/5⌋ = 200\n"
                "   - Divisible by 15: ⌊1000/15⌋ = 66\n"
                "   - Union: 333 + 200 − 66 = 467\n"
                "\n"
                "2. **Divisible by (3 or 5) and by 7:** this means divisible by 21 "
                "or 35.\n"
                "   - Divisible by 21: ⌊1000/21⌋ = 47\n"
                "   - Divisible by 35: ⌊1000/35⌋ = 28\n"
                "   - Divisible by 105: ⌊1000/105⌋ = 9\n"
                "   - Union: 47 + 28 − 9 = 66\n"
                "\n"
                "3. **Subtract:** 467 − 66 = 401\n"
                "\n"
                "Answer: 401",
            },
        },
    },
]


#: The probe's opening answers, oldest first, as it asked them (times are set when the desk opens).
PROBES: list[dict[str, Any]] = [
    {
        "q": "q01",
        "context": "clean",
        "got": 1471.0,
        "correct": True,
        "seconds": 3.35,
        "cost": 0.001924,
        "text": "1471",
    },
    {
        "q": "q01",
        "context": "noisy",
        "got": 1471.0,
        "correct": True,
        "seconds": 3.51,
        "cost": 0.00194,
        "text": "1471",
    },
    {
        "q": "q02",
        "context": "clean",
        "got": 210.0,
        "correct": True,
        "seconds": 3.02,
        "cost": 0.001328,
        "text": "210",
    },
    {
        "q": "q02",
        "context": "noisy",
        "got": 210.0,
        "correct": True,
        "seconds": 3.33,
        "cost": 0.001494,
        "text": "210",
    },
    {
        "q": "q03",
        "context": "clean",
        "got": 13.0,
        "correct": True,
        "seconds": 2.54,
        "cost": 0.001948,
        "text": "13",
    },
    {
        "q": "q03",
        "context": "noisy",
        "got": 13.0,
        "correct": True,
        "seconds": 3.37,
        "cost": 0.002002,
        "text": "13",
    },
    {
        "q": "q04",
        "context": "clean",
        "got": 12.0,
        "correct": True,
        "seconds": 4.61,
        "cost": 0.001302,
        "text": "12",
    },
    {
        "q": "q04",
        "context": "noisy",
        "got": 12.0,
        "correct": True,
        "seconds": 3.49,
        "cost": 0.001967,
        "text": "12",
    },
    {
        "q": "q05",
        "context": "clean",
        "got": 210.0,
        "correct": True,
        "seconds": 2.39,
        "cost": 0.00135,
        "text": "210",
    },
    {
        "q": "q05",
        "context": "noisy",
        "got": 210.0,
        "correct": True,
        "seconds": 2.38,
        "cost": 0.001382,
        "text": "210",
    },
    {
        "q": "q06",
        "context": "clean",
        "got": 97.2,
        "correct": True,
        "seconds": 4.2,
        "cost": 0.001039,
        "text": "97.20",
    },
    {
        "q": "q06",
        "context": "noisy",
        "got": 97.2,
        "correct": True,
        "seconds": 3.37,
        "cost": 0.001759,
        "text": "97.2",
    },
    {
        "q": "q07",
        "context": "clean",
        "got": 46.0,
        "correct": True,
        "seconds": 3.45,
        "cost": 0.00202,
        "text": "46",
    },
    {
        "q": "q07",
        "context": "noisy",
        "got": 46.0,
        "correct": True,
        "seconds": 3.47,
        "cost": 0.002119,
        "text": "46",
    },
    {
        "q": "q08",
        "context": "clean",
        "got": 48.0,
        "correct": True,
        "seconds": 2.51,
        "cost": 0.001854,
        "text": "48",
    },
    {
        "q": "q08",
        "context": "noisy",
        "got": 48.0,
        "correct": True,
        "seconds": 3.47,
        "cost": 0.001933,
        "text": "48",
    },
    {
        "q": "q09",
        "context": "clean",
        "got": 2.0,
        "correct": True,
        "seconds": 3.4,
        "cost": 0.002012,
        "text": "2",
    },
    {
        "q": "q09",
        "context": "noisy",
        "got": 2.0,
        "correct": True,
        "seconds": 3.42,
        "cost": 0.002073,
        "text": "2",
    },
    {
        "q": "q10",
        "context": "clean",
        "got": 20.0,
        "correct": True,
        "seconds": 2.41,
        "cost": 0.001545,
        "text": "20",
    },
    {
        "q": "q10",
        "context": "noisy",
        "got": 20.0,
        "correct": True,
        "seconds": 3.24,
        "cost": 0.001543,
        "text": "20",
    },
    {
        "q": "q11",
        "context": "clean",
        "got": 60.0,
        "correct": True,
        "seconds": 2.97,
        "cost": 0.001455,
        "text": "60",
    },
    {
        "q": "q11",
        "context": "noisy",
        "got": 60.0,
        "correct": True,
        "seconds": 4.51,
        "cost": 0.003318,
        "text": "60",
    },
    {
        "q": "q12",
        "context": "clean",
        "got": 7.5,
        "correct": True,
        "seconds": 2.35,
        "cost": 0.001534,
        "text": "7.5",
    },
    {
        "q": "q12",
        "context": "noisy",
        "got": 7.5,
        "correct": True,
        "seconds": 3.02,
        "cost": 0.006527,
        "text": "7.5",
    },
    {
        "q": "q13",
        "context": "clean",
        "got": 68346304.0,
        "correct": True,
        "seconds": 4.03,
        "cost": 0.002774,
        "text": "68,346,304",
    },
    {
        "q": "q13",
        "context": "noisy",
        "got": 68346304.0,
        "correct": True,
        "seconds": 3.18,
        "cost": 0.002917,
        "text": "68,346,304",
    },
    {
        "q": "q14",
        "context": "clean",
        "got": 3739619.0,
        "correct": True,
        "seconds": 2.99,
        "cost": 0.002179,
        "text": "3739619",
    },
    {
        "q": "q14",
        "context": "noisy",
        "got": 3739619.0,
        "correct": True,
        "seconds": 4.06,
        "cost": 0.002126,
        "text": "3739619",
    },
    {
        "q": "q15",
        "context": "clean",
        "got": 653.0,
        "correct": True,
        "seconds": 7.62,
        "cost": 0.005277,
        "text": "653",
    },
    {
        "q": "q15",
        "context": "noisy",
        "got": 653.0,
        "correct": True,
        "seconds": 5.74,
        "cost": 0.003418,
        "text": "653",
    },
    {
        "q": "q16",
        "context": "clean",
        "got": 11.0,
        "correct": True,
        "seconds": 3.17,
        "cost": 0.002891,
        "text": "11",
    },
    {
        "q": "q16",
        "context": "noisy",
        "got": 6.0,
        "correct": False,
        "seconds": 3.75,
        "cost": 0.006563,
        "text": "6",
    },
    {
        "q": "q17",
        "context": "clean",
        "got": 76.0,
        "correct": True,
        "seconds": 3.84,
        "cost": 0.002791,
        "text": "76",
    },
    {
        "q": "q17",
        "context": "noisy",
        "got": 41.0,
        "correct": False,
        "seconds": 4.13,
        "cost": 0.00284,
        "text": "41",
    },
    {
        "q": "q18",
        "context": "clean",
        "got": 173.0,
        "correct": True,
        "seconds": 3.82,
        "cost": 0.006333,
        "text": "173",
    },
    {
        "q": "q18",
        "context": "noisy",
        "got": 173.0,
        "correct": True,
        "seconds": 2.38,
        "cost": 0.001461,
        "text": "173",
    },
    {
        "q": "q19",
        "context": "clean",
        "got": 2.0,
        "correct": True,
        "seconds": 4.0,
        "cost": 0.006342,
        "text": "2",
    },
    {
        "q": "q19",
        "context": "noisy",
        "got": 2.0,
        "correct": True,
        "seconds": 2.87,
        "cost": 0.002367,
        "text": "2",
    },
    {
        "q": "q20",
        "context": "clean",
        "got": 401.0,
        "correct": True,
        "seconds": 5.11,
        "cost": 0.008046,
        "text": "401",
    },
    {
        "q": "q20",
        "context": "noisy",
        "got": 401.0,
        "correct": True,
        "seconds": 4.32,
        "cost": 0.001692,
        "text": "401",
    },
    {
        "q": "q01",
        "context": "clean",
        "got": 1471.0,
        "correct": True,
        "seconds": 2.44,
        "cost": 0.001821,
        "text": "1471",
    },
    {
        "q": "q01",
        "context": "noisy",
        "got": 1471.0,
        "correct": True,
        "seconds": 2.49,
        "cost": 0.001706,
        "text": "1471",
    },
    {
        "q": "q02",
        "context": "clean",
        "got": 210.0,
        "correct": True,
        "seconds": 3.07,
        "cost": 0.001456,
        "text": "210",
    },
    {
        "q": "q02",
        "context": "noisy",
        "got": 210.0,
        "correct": True,
        "seconds": 3.01,
        "cost": 0.000981,
        "text": "210",
    },
    {
        "q": "q03",
        "context": "clean",
        "got": 13.0,
        "correct": True,
        "seconds": 2.58,
        "cost": 0.001762,
        "text": "13",
    },
    {
        "q": "q03",
        "context": "noisy",
        "got": 13.0,
        "correct": True,
        "seconds": 3.3,
        "cost": 0.001926,
        "text": "13",
    },
    {
        "q": "q04",
        "context": "clean",
        "got": 12.0,
        "correct": True,
        "seconds": 2.44,
        "cost": 0.00172,
        "text": "12",
    },
    {
        "q": "q04",
        "context": "noisy",
        "got": 12.0,
        "correct": True,
        "seconds": 3.76,
        "cost": 0.001977,
        "text": "12",
    },
]
