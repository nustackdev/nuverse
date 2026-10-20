"""The Larkspur base as it opens: pages, facts and glossary, content only.

Dates are day offsets from the day the base is first opened (negative is past), resolved at seed.
"""

from __future__ import annotations


__all__ = ["DOCS", "FACTS", "GLOSSARY", "PEOPLE"]

#: slug -> (name, role)
PEOPLE = {
    "mara": ("Mara Okafor", "Founder and CEO"),
    "theo": ("Theo Lindqvist", "Hardware lead"),
    "ines": ("Ines Duarte", "Design lead"),
    "ravi": ("Ravi Menon", "Firmware"),
    "sol": ("Sol Park", "App engineer, iOS and Android"),
    "june": ("June Halvorsen", "Ops and support"),
    "arlo": ("Arlo Bennett", "Growth"),
}

#: key -> {label, value, owner, note}. value is the string shown. Dates in values: "{date:+28}" (resolved at seed to eg "Nov 17").
FACTS = {
    "price": {
        "label": "Sensor price",
        "value": "$89",
        "owner": "arlo",
        "note": "Per sensor, before tax. Set in D2.",
    },
    "plan-price": {
        "label": "App plan price",
        "value": "$6 a month",
        "owner": "arlo",
        "note": "Per garden, any number of sensors. First three months free with a kit. Set in D3.",
    },
    "launch-date": {
        "label": "v2 launch date",
        "value": "{date:+28}",
        "owner": "mara",
        "note": "Public launch of Fieldnote v2. Only Mara moves it.",
    },
    "battery-life": {
        "label": "Battery life claim",
        "value": "14 months",
        "owner": "theo",
        "note": "One reading every 15 minutes on the 2600 mAh cell. Sign-off pending in the battery push.",
    },
    "pilot-units": {
        "label": "Sensors in the co-op pilot",
        "value": "240",
        "owner": "june",
        "note": "Installed and paired, including spares in the field.",
    },
    "pilot-sites": {
        "label": "Pilot sites",
        "value": "12 gardens",
        "owner": "june",
        "note": "All in the Riverside Garden Co-op, one gateway each.",
    },
    "support-hours": {
        "label": "Support hours",
        "value": "8:00 to 18:00 CET, weekdays",
        "owner": "june",
        "note": "Set in D8. Outages outside hours page the on-call.",
    },
    "oncall": {
        "label": "On-call this week",
        "value": "Ravi Menon",
        "owner": "ravi",
        "note": "Rotates Monday to Monday. Update when the rota moves.",
    },
    "gateway-range": {
        "label": "Gateway range",
        "value": "2 km in open field",
        "owner": "theo",
        "note": "Line of sight at SF10. Plan on 600 m through houses and hedges.",
    },
    "coop-discount": {
        "label": "Co-op discount",
        "value": "20%",
        "owner": "arlo",
        "note": "Proposed in D7, not final. Orders of 50 sensors or more.",
    },
    "stale-days": {
        "label": "Pages go stale after (days)",
        "value": "60",
        "owner": "ines",
        "note": "Pages not edited for this long show up in the stale list.",
    },
    "runway": {
        "label": "Runway",
        "value": "19 months",
        "owner": "mara",
        "note": "At current burn, before launch revenue. Updated monthly.",
    },
    "support-email": {
        "label": "Support email",
        "value": "help@fieldnote.example",
        "owner": "june",
        "note": "Goes to the help desk. Never give out personal addresses.",
    },
    "min-android": {
        "label": "Lowest Android version",
        "value": "Android 10",
        "owner": "sol",
        "note": "For the v2 app, if D6 passes. v1 still runs on Android 9.",
    },
    "min-ios": {
        "label": "Lowest iOS version",
        "value": "iOS 16",
        "owner": "sol",
        "note": "Covers about 97% of iPhones in the pilot.",
    },
    "release-train": {
        "label": "App release train",
        "value": "every second Thursday",
        "owner": "sol",
        "note": "App only. Firmware goes out in rings, see D4.",
    },
    "probe-depth": {
        "label": "Probe depth",
        "value": "12 cm",
        "owner": "theo",
        "note": "Push the probe in to the line. Calibration assumes this depth.",
    },
}

#: (term, definition) pairs
GLOSSARY = [
    (
        "LoRa",
        "A long-range, low-power radio. Each probe sends a few bytes to a gateway every 15 minutes and sleeps the rest of the time.",
    ),
    (
        "Gateway",
        "The box that receives LoRa from every probe on a site and forwards readings over the garden's internet. One gateway serves a whole garden.",
    ),
    (
        "Probe",
        "The Fieldnote sensor itself: a stake with two electrodes, a cell, and a radio in the cap. You push it into the bed to the depth line.",
    ),
    (
        "VWC",
        "Volumetric water content: the volume of water in a volume of soil, as a percent. This is the number the app shows.",
    ),
    (
        "Field capacity",
        "The water a soil still holds after the extra has drained away, usually a day or two after a soaking. Watering above it is wasted.",
    ),
    (
        "Wilting point",
        "The water content below which plants can no longer pull water from the soil and wilt without recovering.",
    ),
    (
        "Sync window",
        "The short slot after a probe sends when it listens for the gateway. Settings and firmware updates only arrive in this window.",
    ),
    (
        "Sleep current",
        "What a probe draws between readings, in microamps. It decides most of the battery life.",
    ),
    (
        "OTA",
        "Over the air: updating firmware on probes in the field through the gateway, without touching them.",
    ),
    (
        "Ring",
        "A rollout stage for firmware. Ring 0 is our own sensors, ring 1 is a fixed 10% of the field, ring 2 is everyone.",
    ),
    (
        "RMA",
        "Return merchandise authorization: the ticket and number we give a customer before they send back a broken unit.",
    ),
    (
        "Calibration curve",
        "The mapping from the probe's raw reading to VWC for a soil type. Clay, loam and sand each have their own.",
    ),
    ("Pilot site", "A garden in the co-op pilot, with its own gateway and coordinator."),
    (
        "Plot",
        "What co-op growers call their own patch inside a shared garden. One plot usually holds several beds.",
    ),
    (
        "Co-op",
        "A group of growers sharing land, tools and often one budget. One coordinator usually speaks for all of them.",
    ),
    (
        "Bed",
        "A single planted strip or raised box. The app tracks moisture per bed, one or more probes each.",
    ),
    ("mAh", "Milliamp hours, a measure of battery capacity. Our cell holds 2600 mAh."),
    (
        "Appetite",
        "From Shape Up: how much time a piece of work is worth to us, set before we start. Fixed time, variable scope.",
    ),
]

#: Every page. kind: wiki | project | meeting | decision | person | note. updated and created are day offsets (<= 0).
#: editor: who last edited. status: projects "active" / "paused" / "done"; decisions "open" / "decided"; others "".
#: date: meetings only, day offset of the meeting; "{date}" in a title is replaced by it (eg "Weekly sync, Oct 13").
DOCS = [
    # ------------------------------------------------------------------ handbook
    {
        "slug": "welcome",
        "title": "Welcome to Larkspur",
        "kind": "wiki",
        "owner": "mara",
        "editor": "mara",
        "tags": ["start-here"],
        "status": "",
        "created": -420,
        "updated": -6,
        "body": """\
## Start here

Larkspur is seven people making Fieldnote: a soil-moisture probe you push into a garden bed, and an app that tells you when to water. The probe talks LoRa to a shared gateway, so a whole garden runs on one box on a shed roof.

We are a few weeks from shipping v2. Launch is {{launch-date}}, and everything about it lives on [[v2-launch]]. We have {{runway}} of runway, so this one matters.

## Read these first

1. [[how-we-work]]: the week, syncs, how decisions get made
2. [[onboarding]]: your first two weeks, day by day
3. [[writing-here]]: how this wiki works, two minutes
4. [[pricing]]: what we charge and why

## Who to ask

| Person | Ask about |
|---|---|
| @mara | money, hiring, the launch date |
| @theo | the probe, battery, enclosure |
| @ines | app design, this wiki |
| @ravi | firmware, on-call |
| @sol | iOS, Android, releases |
| @june | support, the co-op pilot |
| @arlo | pricing, interviews, launch posts |

## What changed lately

{{query recent 8}}
""",
    },
    {
        "slug": "how-we-work",
        "title": "How we work",
        "kind": "wiki",
        "owner": "mara",
        "editor": "june",
        "tags": ["start-here", "process"],
        "status": "",
        "created": -400,
        "updated": -12,
        "body": """\
## The week

- Monday 10:00: weekly sync, 30 minutes. Notes go on a meeting page the same day. The latest is [[m-sync-4]].
- The app ships {{release-train}}, see [[release-process]].
- Firmware goes out in rings, never to everyone at once ([[d04-rings]]).
- Friday afternoon is cleanup: close tasks, fix pages, no meetings.

## Decisions

Anything that costs more than a week or is hard to undo gets a decision page. Write the context, the options, and a proposal. Say who decides. Leave it open for at least two working days so people can comment. Then the owner decides, writes down the date, and we move on.

Disagree on the page, not in DMs. "I disagree but let's go" is a fine thing to write.

{{query open-decisions}}

## Writing

If you explained the same thing to two people, it belongs on a page. Keep it short and plain, see [[brand-voice]].

## Tasks

Tasks live on the page where they came up, with one owner and one due date. If it slips, move the date and add one line on why. Nobody gets in trouble for a moved date. People get in trouble for a silent one.
""",
    },
    {
        "slug": "onboarding",
        "title": "Onboarding: your first two weeks",
        "kind": "wiki",
        "owner": "june",
        "editor": "june",
        "tags": ["start-here", "people"],
        "status": "",
        "created": -300,
        "updated": -20,
        "body": """\
## Week one

- **Day 1:** laptop, accounts, read [[welcome]] and [[how-we-work]]. Lunch with whoever is in.
- **Day 2:** take a Fieldnote home. Push the probe into a pot or a bed ({{probe-depth}}, to the line), pair it, and watch the first readings come in. Write down everything that confused you. We want that list.
- **Day 3:** shadow support for a full shift with @june. Read the [[support-runbook]] first.
- **Day 4:** lab walkthrough with @theo. Read [[lab-rules]] before you touch the bench.
- **Day 5:** sit in on the weekly sync. Ask the dumb questions. They usually aren't.

## Week two

- Ship something small: a copy fix, a page, a log line. Anything that goes through the real process.
- Read [[security-basics]] and turn on 2FA everywhere.
- Visit a pilot garden if one is near you. Bring gloves.
- The trip goes on [[expenses]].

## Who to ask

Your buddy first. Then the team channel. Then whoever owns the page you are stuck on (it says at the top).
""",
    },
    {
        "slug": "writing-here",
        "title": "Writing in this wiki",
        "kind": "wiki",
        "owner": "ines",
        "editor": "ines",
        "tags": ["start-here", "wiki"],
        "status": "",
        "created": -200,
        "updated": -3,
        "body": """\
## The short version

This wiki is plain markdown with a few extras that keep pages alive. You can learn all of it in two minutes.

## Links

Put a page's slug in double square brackets and it becomes a link: [[pricing]]. Add a bar for a different label: [[how-we-work|how we run the week]]. If you link a page that doesn't exist yet, the health check flags it. Fine for a day, not for a month.

## Facts

Some values show up everywhere: the price, the launch date, support hours. We keep each one once, as a fact, and pages pull it in with double curly braces. Our launch date is {{launch-date}}. When it moves, every page moves with it. Never type a fact by hand. Here is the full list:

{{query facts}}

## Mentions and tasks

Type @ and a name to mention someone, like @ines. A task is a checkbox line with one owner and a due date counted in days from today. The app turns that into a real date and puts it in the owner's list:

- [ ] Add glossary entries for plot and bed @ines due:+5

## Queries

A query on its own line becomes a live table. This one lists pages nobody has edited in {{stale-days}} days:

{{query stale}}

If your page shows up there, update it or ask [[ines|me]] to delete it.
""",
    },
    {
        "slug": "pricing",
        "title": "Pricing",
        "kind": "wiki",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["pricing", "growth"],
        "status": "",
        "created": -75,
        "updated": -9,
        "body": """\
## What we charge

| Item | Price | Where it was decided |
|---|---|---|
| Fieldnote sensor | {{price}} | [[d02-price]] |
| App plan, per garden | {{plan-price}} | [[d03-plan]] |
| Co-op discount (proposed) | {{coop-discount}} | [[d07-coop-discount]] |

The gateway ships free in the starter kit with four sensors. Extra gateways are sold at cost.

## Why these numbers

The sensor is priced so a small farm can buy six without a meeting with their accountant. The plan pays for servers and support, not for hardware. We worked this out in the [[m-pricing|pricing workshop]] and from about forty grower interviews.

## Rules

- No discounts by DM. If a customer asks, send them to [[arlo]].
- No lifetime deals. We have said no twice already and will keep saying it.
- The EU shop shows prices with VAT, the US shop without sales tax.
- When a price changes, change the fact, not this page.
""",
    },
    {
        "slug": "support-runbook",
        "title": "Support runbook",
        "kind": "wiki",
        "owner": "june",
        "editor": "june",
        "tags": ["support", "process"],
        "status": "",
        "created": -150,
        "updated": -15,
        "body": """\
## Hours and channels

We answer {{support-hours}}. Mail goes to {{support-email}}. Outside hours, firmware and gateway outages page the on-call ({{oncall}} this week, see [[on-call]]). Everything else waits for the morning. Hours were set in [[d08-support-hours]].

## First reply

- Reply within 4 working hours. A human reply, not a template, even if it is two lines.
- Ask for the sensor ID (on the sticker, starts with FN2-) and the garden name.
- Check the gateway's last-seen time before anything else. Half of all "dead sensor" tickets are a gateway that lost power.

## Common cases

| Symptom | First check | Then |
|---|---|---|
| No readings | Gateway last seen | Re-pair the probe |
| Stuck at 0% | Probe depth, soil contact | Swap the probe |
| Battery gone in weeks | Firmware version | Escalate to firmware |
| Cracked case | Ask for a photo | Start an RMA |

## Returns

Broken in normal use means a free replacement. Coverage terms will get a warranty page of their own; until then, tell people {{warranty-years}} and log the ticket. Anything from a [[coop-pilot]] garden goes straight to [[june]].

- [ ] Write macros for the five most common tickets @june due:+4
""",
    },
    {
        "slug": "on-call",
        "title": "On-call",
        "kind": "wiki",
        "owner": "ravi",
        "editor": "ravi",
        "tags": ["firmware", "process"],
        "status": "",
        "created": -140,
        "updated": -8,
        "body": """\
## Who

One person per week, Monday to Monday. This week it is {{oncall}}. The rota goes [[ravi|Ravi]], [[sol|Sol]], [[theo|Theo]], then around again. Swaps are fine, write them here.

## What pages you

- Gateways: more than 10% of the fleet silent for 30 minutes.
- Ingest: no readings stored for 10 minutes.
- Firmware: ring alarms during a rollout ([[d04-rings]]).

Customer tickets never page anyone. They wait for support hours ({{support-hours}}) and June's team, see the [[support-runbook]].

## When paged

1. Ack within 15 minutes.
2. Check the status board. Is it us, or the garden's internet?
3. If a firmware ring is rolling, pause it first and ask questions after:

```
fnctl ota pause --ring all
```

4. Write two lines in the incident log before you go back to sleep.

## After

Every page gets a short note within two days: what happened, what we changed. Keys and access rules are in [[security-basics]].
""",
    },
    {
        "slug": "release-process",
        "title": "Release process",
        "kind": "wiki",
        "owner": "sol",
        "editor": "sol",
        "tags": ["app", "process"],
        "status": "",
        "created": -160,
        "updated": -25,
        "body": """\
## App

The app ships {{release-train}}. The train leaves whether your feature is on it or not.

- **Monday before:** branch cut. Only fixes after this.
- **Tuesday:** QA on the device shelf. The oldest phones we test are {{min-ios}} and {{min-android}}. The Android floor is up for change in [[d06-android]].
- **Wednesday:** submit to both stores.
- **Thursday:** staged rollout at 10%, then 100% after 24 hours if crash-free sessions stay above 99.5%.

## Firmware

Firmware does not ride the train. It goes out in rings, see [[d04-rings]] and [[firmware-ota]]. If a firmware change needs an app change, the app ships first.

## Hardware

Anything physical follows the [[shipping-checklist]].

## Hotfixes

A hotfix skips the train with a yes from @sol or @mara. Write the reason on the release page. We did three last quarter, which is three too many.
""",
    },
    {
        "slug": "shipping-checklist",
        "title": "Shipping checklist",
        "kind": "wiki",
        "owner": "theo",
        "editor": "theo",
        "tags": ["hardware", "process"],
        "status": "",
        "created": -170,
        "updated": -30,
        "body": """\
Run this before any batch of hardware leaves the building, pilot or retail.

## Per batch

1. Firmware on every unit matches the current ring 2 build.
2. Sleep current spot-check on 5 units per 100. Pass is under 22 uA.
3. Probe marked at {{probe-depth}}, depth line visible.
4. Gasket seated, case screws at 0.4 Nm.
5. Cell voltage between 3.55 and 3.65 V.
6. Range test from the loading dock to the gateway on the roof.
7. Labels: sensor ID, QR code, CE mark.
8. Box has the quick start card and a spare gasket.

## Sign-off

Two names on the batch sheet, and neither is the person who built it. Bench rules are in [[lab-rules]]. Battery numbers come from [[battery-push]]. App releases have their own steps in [[release-process]].

- [x] Add the sleep current spot-check to the batch sheet @theo due:-9
- [ ] Get the v2 quick start card printed @ines due:+6
""",
    },
    {
        "slug": "brand-voice",
        "title": "Brand voice",
        "kind": "wiki",
        "owner": "ines",
        "editor": "arlo",
        "tags": ["design", "growth"],
        "status": "",
        "created": -250,
        "updated": -40,
        "body": """\
## How Fieldnote sounds

Like a neighbor who grows good tomatoes. Knows things, doesn't lecture.

- Short sentences. One idea each.
- Say what to do: "Water bed 3 tonight", not "Moisture levels are suboptimal".
- Use numbers when they help, in units growers use: percent, days, centimeters.
- No exclamation marks in the app. One per email, at most.
- We say garden, bed, probe. Not deployment, zone, device.

## Words we don't use

| Instead of | Say |
|---|---|
| smart irrigation solution | sensor |
| optimize | water less |
| ecosystem | app |
| users | growers |

## Where it applies

App copy, support replies, the site, launch posts. @arlo owns the site, @ines owns app copy, @june owns support macros. When in doubt, read it aloud. If it sounds like a bank, rewrite it.

Good examples: the [[support-runbook]] and [[pricing]]. This wiki follows the same rules ([[writing-here]]).
""",
    },
    {
        "slug": "tools",
        "title": "Tools we use",
        "kind": "wiki",
        "owner": "june",
        "editor": "june",
        "tags": ["ops"],
        "status": "",
        "created": -260,
        "updated": -50,
        "body": """\
## What we use

| Tool | For | Owner |
|---|---|---|
| This wiki | everything written down | @ines |
| GitHub | code, firmware, issues | @ravi |
| Figma | app and print design | @ines |
| Slack | chat, the alerts channel | @june |
| Help desk | the support inbox | @june |
| Fieldnote admin | sensors, gateways, RMAs | @sol |
| Google Workspace | mail, calendar, sheets | @mara |

## Rules

- Ask @june before adding a paid tool. Most of what we need we already pay for.
- Turn on 2FA, see [[security-basics]].
- If it is a decision, it goes on a page, not in chat. See [[how-we-work]].
- Leaving a tool? Export first, then cancel. We lost a year of design history to a cancelled plan once.
""",
    },
    {
        "slug": "interviews-guide",
        "title": "Customer interviews guide",
        "kind": "wiki",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["growth", "research"],
        "status": "",
        "created": -120,
        "updated": -33,
        "body": """\
## Why we interview

Every two weeks each of us talks to one grower. Not to sell. To learn how they water now and what it costs them.

## Before

- Pick someone who watered a garden this month. Growers from the [[coop-pilot]] are easy, but also find people who have never heard of us.
- Write down three things you want to learn. Things, not questions.

## During

- Ask about the last time, not about "would you". "When did you last lose plants to dry soil?" beats "Would you pay for alerts?"
- No pitching until the last five minutes, and only if they ask.
- Write down their exact words. "I walk the beds with my thumb" is worth more than "manual checks".
- Compliments are noise. Commitments are signal: a pilot, an intro, a pre-order.

## After

Write it up the same day, ten lines, tagged interview. @arlo reads all of them on Friday. Copy that comes out of interviews still goes through [[brand-voice]].

Background reading: Ines's notes on [[n-mom-test]].
""",
    },
    {
        "slug": "lab-rules",
        "title": "Hardware lab rules",
        "kind": "wiki",
        "owner": "theo",
        "editor": "theo",
        "tags": ["hardware", "lab"],
        "status": "",
        "created": -260,
        "updated": -131,
        "body": """\
## Before you touch the bench

- Read this page. Then tell @theo you read it.
- Safety glasses for anything with a soldering iron or a cell out of its holder.
- Lithium primary cells do not get charged, shorted, or punctured. Ever. Damaged cells go in the red sand bucket, not the bin.

## Bench

- Leave the bench how you found it. Iron off, fume extractor off.
- Label every unit with your name and the date. Unlabeled units older than a week go in the parts box.
- The power analyzer is booked in the calendar. Sleep current runs take 12 hours, so book overnight.

## Cold chamber

It goes down to -20 C. Never leave it running over a weekend without a note on the door saying who, what, and until when.

## Shipping

Anything that leaves the lab follows the [[shipping-checklist]]. Pull test units from the current batch, never from your own drawer. The door code policy is in [[security-basics]].
""",
    },
    {
        "slug": "expenses",
        "title": "Travel and expenses",
        "kind": "wiki",
        "owner": "mara",
        "editor": "mara",
        "tags": ["ops", "people"],
        "status": "",
        "created": -380,
        "updated": -204,
        "body": """\
## Travel

- Train over plane for anything under 6 hours.
- Book through the shared account. Keep receipts as photos.
- Hotels up to 120 EUR a night, 160 in capitals.
- Garden visits count as work travel. Mileage at 0.30 EUR per km.

## Gear

Under 200 EUR, just buy it and file the receipt. Over that, ask [[mara]] first. Lab parts go through @theo so we don't buy the same cells twice.

## Filing

Submit by the 5th of the next month. Late is fine, lost is not. Questions go to @june.

## Not covered

Upgrades, minibars, and anything you would be embarrassed to explain at the sync.

How this fits the rest of the week is in [[how-we-work]]. New people get walked through it in [[onboarding]].
""",
    },
    {
        "slug": "security-basics",
        "title": "Security basics",
        "kind": "wiki",
        "owner": "ravi",
        "editor": "ravi",
        "tags": ["security", "process"],
        "status": "",
        "created": -230,
        "updated": -97,
        "body": """\
## Accounts

- 2FA on everything, with an app or a hardware key. No SMS.
- Shared logins live in the password manager. Not in chat, not in this wiki, not on a sticky note on the lab monitor.
- When someone leaves, their accounts close the same day.

## Code and firmware

- Firmware signing keys live on two hardware keys. @ravi holds one, @theo the other. Nobody else.
- Only signed builds run on customer devices. The update server rejects anything else ([[firmware-ota]]).
- No customer data on laptops. Exports go to the shared drive and get deleted after 30 days.

## Customer data

We store readings, garden names, and an email. No addresses unless they buy hardware. Support can see a garden; only @june and @ravi can delete one.

## Lab

The lab door code changes every quarter and is never written down outside the password manager.

## If something looks wrong

Tell the on-call right away ([[on-call]]). Don't try to fix it quietly.
""",
    },
    # ------------------------------------------------------------------ projects
    {
        "slug": "v2-launch",
        "title": "Fieldnote v2 launch",
        "kind": "project",
        "owner": "mara",
        "editor": "theo",
        "tags": ["launch", "v2"],
        "status": "active",
        "created": -100,
        "updated": -2,
        "body": """\
## Goal

Ship Fieldnote v2 to the public on {{launch-date}}: new probe, new enclosure, staged firmware, a first-run that takes minutes. Sell 1,500 sensors in the first 90 days.

## Why

v1 proved growers want this. It also proved our battery claim was wrong (8 months, not 12), setup took 25 minutes, and every firmware update was a held breath. v2 fixes all three. With {{runway}} of runway we get about one more swing like this, so it has to land.

## Scope

- **In:** probe and enclosure v3, a {{battery-life}} battery claim we can stand behind, ring rollouts, the new first-run, co-op pricing.
- **Out:** valve control, a web dashboard, any plan tier above the base plan.

## Milestones

| Milestone | Owner | When | Status |
|---|---|---|---|
| Firmware rings live | @ravi | 4 weeks ago | done |
| Onboarding v2 in beta | @sol | in 7 days | on track |
| Battery claim signed off | @theo | in 10 days | at risk |
| Co-op terms final | @arlo | in 12 days | open |
| First retail batch shipped | @theo | in 21 days | on track |
| Public launch | @mara | {{launch-date}} | on track |

## Workstreams

- [[battery-push]]
- [[onboarding-redesign]]
- [[coop-pilot]]
- [[firmware-ota]] (done)

## Risks

- The second cell ([[d05-second-cell]]) is not qualified. If the first supplier slips again, so do we.
- Dropping Android 9 ([[d06-android]]) will annoy a few loud pilot growers.
- Retail boxes are late. Nothing ships without a box.

## Tasks

- [x] Lock v2 feature scope @mara due:-16
- [ ] Order 2,000 retail boxes @theo due:-2
- [ ] Launch post and press list @arlo due:+14
- [ ] Final go or no-go call @mara due:+21

## Due this week

{{query tasks-due 7}}

## Everything on this project

{{query project v2-launch}}
""",
    },
    {
        "slug": "battery-push",
        "title": "Battery life push",
        "kind": "project",
        "owner": "theo",
        "editor": "theo",
        "tags": ["battery", "hardware", "firmware"],
        "status": "active",
        "created": -60,
        "updated": -4,
        "body": """\
## Goal

Make the {{battery-life}} claim true on every unit, through a cold winter, with margin. Sign-off in about ten days.

## Why

v1 promised 12 months and averaged 8. That cost us about 60 RMAs and a lot of goodwill in the pilot. We are not doing that twice.

## Where we are

Budget: one reading every 15 minutes, 96 a day, on a 2600 mAh cell with about 2420 mAh usable.

| Item | v1 firmware | Now | With adaptive data rate |
|---|---|---|---|
| Sleep current | 31 uA | 18 uA | 18 uA |
| Energy per reading | 0.071 mAh | 0.055 mAh | 0.046 mAh (ring 0) |
| Projected life, 20 C | 10.5 months | 14.0 months | 16.4 months |
| Projected life, -10 C | 9.5 months | 12.5 months | 14.8 months |

So: room temperature passes today, cold passes only with adaptive data rate. That is the whole project now.

## Scope

- **Firmware:** sleep regression (fixed), adaptive data rate so close probes send at a faster spreading factor.
- **Hardware:** a second cell ([[d05-second-cell]]), six weeks in the cold chamber, an aging test.
- **Not in scope:** a bigger cell. The enclosure is final.

## Milestones

| Milestone | When | Status |
|---|---|---|
| Sleep current fixed | 3 weeks ago | done |
| Adaptive data rate in ring 1 | this week | in progress |
| Cold chamber, week 6 | in 9 days | running |
| Cell B qualified or dropped | in 12 days | open |

## Risks

- Cell A lead time went from 6 to 11 weeks.
- If adaptive data rate doesn't hold up in ring 1, we lower the claim. We don't bury the cold number.

## Tasks

- [x] Ship the sleep current fix to ring 2 @ravi due:-20
- [ ] Adaptive data rate build to ring 1 @ravi due:+2
- [ ] Cold chamber week 6 readout @theo due:+9

Latest numbers were walked through in [[m-battery-review]]. This feeds the claim on [[v2-launch]].

{{query project battery-push}}
""",
    },
    {
        "slug": "coop-pilot",
        "title": "Garden co-op pilot",
        "kind": "project",
        "owner": "june",
        "editor": "june",
        "tags": ["pilot", "coop", "support"],
        "status": "active",
        "created": -50,
        "updated": -3,
        "body": """\
## Goal

Run {{pilot-units}} sensors across {{pilot-sites}} of the Riverside Garden Co-op for eight weeks, and learn what a co-op needs that a single farm doesn't.

## Why

Co-ops are our cheapest way in: one gateway per site, many growers, one coordinator who decides. If the pilot works, co-ops become a sales channel and not just a nice story.

## Scope

- One gateway per site, 8 to 30 sensors each.
- A shared view for each site coordinator.
- A check-in every week, a retro every four weeks.
- **Out:** per-grower billing. Every site is on one plan for now.

## Milestones

| Week | What | Status |
|---|---|---|
| 0 | Every site installed and paired | done |
| 4 | Retro and fix list | done |
| 6 | Second firmware update through rings | next week |
| 8 | Final retro, renew or not | in 3 weeks |

## What we learned so far

- Coordinators want one weekly email, not 200 alerts.
- Three sites had gateway power trouble, all on shared sheds with someone else's extension cord.
- Growers trust the number more when they can see the probe. Bright flags help.

More in [[m-pilot-retro]] and in Ines's [[n-garden-visits]]. Co-op pricing is being worked out in [[d07-coop-discount]] (proposed: {{coop-discount}} off). Tickets from pilot gardens follow the [[support-runbook]].

## Tasks

- [x] Replace the gateway power supply at Elm Street @june due:-8
- [ ] Draft the weekly coordinator email @june due:+3
- [ ] Renewal conversation with the co-op board @mara due:+19

{{query project coop-pilot}}
""",
    },
    {
        "slug": "onboarding-redesign",
        "title": "App onboarding redesign",
        "kind": "project",
        "owner": "ines",
        "editor": "ines",
        "tags": ["app", "design", "v2"],
        "status": "active",
        "created": -45,
        "updated": -1,
        "body": """\
## Goal

A new grower gets from box to first reading in under 5 minutes, without reading anything. In v1 it took 25 minutes on average and 1 in 6 people gave up.

## Why

Setup is the biggest support topic: 31% of pilot tickets. Every minute we cut is a ticket we don't answer, and a grower who doesn't give up on day one.

## Scope

- New first-run: scan the QR code, name the bed, push the probe, see a live reading.
- Gateway pairing moves behind the scenes on co-op sites.
- Runs on {{min-ios}} and on whatever Android floor [[d06-android]] lands on.
- **Out:** moving v1 accounts. Old users keep the old flow until 2.1.

## Milestones

| Milestone | Owner | Status |
|---|---|---|
| Flows and copy | @ines | done |
| Prototype tested with six growers | @ines | done |
| Built behind a flag | @sol | in progress |
| In beta on both stores | @sol | next week |

## Risks

- The first reading waits for the gateway sync window. If it takes 90 seconds, people think it's broken.
- German copy runs long and breaks two screens.

## Tasks

- [x] Run the prototype with six growers @ines due:-11
- [ ] Build the bed naming screen @sol due:-1
- [ ] Design the waiting state for the first reading @ines due:+1
- [ ] German copy pass @arlo due:+8

Ideas I'm still chewing on: [[n-first-run]]. Crit notes: [[m-design-crit]]. Tone: [[brand-voice]].

{{query project onboarding-redesign}}
""",
    },
    {
        "slug": "firmware-ota",
        "title": "Staged firmware updates",
        "kind": "project",
        "owner": "ravi",
        "editor": "ravi",
        "tags": ["firmware", "ota"],
        "status": "done",
        "created": -110,
        "updated": -26,
        "body": """\
## Goal

Update firmware on every sensor in the field without ever bricking a garden. Done.

## Why

In v1 we pushed to everyone at once. In March one bad build stopped readings on 140 sensors for two days. Never again.

## What we built

- Signed images only, checked on the device before flashing.
- Rings, as decided in [[d04-rings]]: ring 0 is our own 30 sensors, ring 1 is a fixed 10% of the field, ring 2 is everyone.
- Each ring waits 48 hours. A ring pauses by itself if missed readings go above 2%.
- Dual-bank flash: a failed boot falls back to the old image.

## How to roll out

```
fnctl ota push --build 2.4.1 --ring 0
fnctl ota status --ring 0
fnctl ota promote --build 2.4.1 --ring 1
```

Pausing during an incident is on [[on-call]]. App releases work differently, see [[release-process]].

## Milestones

| Milestone | Status |
|---|---|
| Dual-bank bootloader | done |
| Signing and verify | done |
| Ring scheduler and auto-pause | done |
| First real rollout (2.3.0) | done |

## Risks (closed)

- A probe that misses its sync window for a week never gets the update. We now retry for 14 days, then flag it in the admin.

## Tasks

- [x] Auto-pause on missed readings @ravi due:-30

{{query project firmware-ota}}
""",
    },
    # ------------------------------------------------------------------ decisions
    {
        "slug": "d01-lora",
        "title": "D1: LoRa with a shared gateway",
        "kind": "decision",
        "owner": "theo",
        "editor": "theo",
        "tags": ["decision", "radio", "hardware"],
        "status": "decided",
        "created": -200,
        "updated": -180,
        "body": """\
## Context

A probe in a garden bed is far from Wi-Fi, often behind a shed, and has to run on one cell for over a year. We needed a radio that reaches far and sips power.

## Options

| Option | Range | Power | Running cost |
|---|---|---|---|
| Wi-Fi | about 30 m | high | none |
| Bluetooth through a phone | about 10 m | low | someone has to walk the beds |
| Cellular in every probe | anywhere | high | 2 to 4 EUR a month per probe |
| LoRa with a shared gateway | {{gateway-range}} | very low | one gateway per site |

## Decision

LoRa, one gateway per garden or co-op site, plugged into the garden's power and internet. Proposed by @theo with @ravi, signed off by @mara 180 days ago.

## Consequences

- One gateway serves a whole site. That is why co-ops work for us ([[coop-pilot]]).
- Gateway power is now our most common failure, see the [[support-runbook]].
- Low data rate: a reading every 15 minutes, no live streaming. Fine for soil.
- The battery math gets much easier, see [[battery-push]].
""",
    },
    {
        "slug": "d02-price",
        "title": "D2: Sensor price",
        "kind": "decision",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["decision", "pricing"],
        "status": "decided",
        "created": -75,
        "updated": -60,
        "body": """\
## Context

v1 sold at $119 and still lost money on hardware. Growers told us they buy sensors in sixes, and six v1 sensors is over $700. The v2 bill of materials is $31 at 2,000 units.

## Options

1. **Same as v1.** Best margin per unit, but it kills multi-bed gardens.
2. **About 2.9 times the BOM.** Six sensors stay under $550.
3. **Go cheap, charge more for the plan.** Easy entry, but then we live or die on the plan.

## Decision

Option 2: {{price}} per sensor. Decided by @arlo and @mara after the pricing interviews, 60 days ago. The plan stays a separate line, see [[d03-plan]].

## Consequences

- Retail margin is thin. Any co-op discount ([[d07-coop-discount]]) has to come out of volume, not margin.
- The price is a fact in this wiki, so if it changes it changes in one place. Overview on [[pricing]].
""",
    },
    {
        "slug": "d03-plan",
        "title": "D3: The app is a monthly plan",
        "kind": "decision",
        "owner": "mara",
        "editor": "mara",
        "tags": ["decision", "pricing", "app"],
        "status": "decided",
        "created": -70,
        "updated": -58,
        "body": """\
## Context

The sensor is a one-time sale. Servers, the gateway backend and support are not. With {{runway}} of runway we need money that comes in every month, not only at launch.

## Options

1. **Free app forever**, cost baked into the hardware price.
2. **Monthly plan per garden**, any number of sensors.
3. **Subscription per sensor.**

## Decision

Option 2: {{plan-price}} per garden. The first three months are free with a new kit. Decided by @mara 58 days ago, after @arlo ran the numbers next to [[d02-price]].

## Consequences

- Per garden keeps big gardens and co-ops simple. Per sensor punished exactly the people we want.
- We have to earn it every month. The app has to be worth opening in February.
- Co-ops pay per site; whether they get a discount is [[d07-coop-discount]]. The full picture is on [[pricing]].
""",
    },
    {
        "slug": "d04-rings",
        "title": "D4: Roll firmware out in rings",
        "kind": "decision",
        "owner": "ravi",
        "editor": "ravi",
        "tags": ["decision", "firmware", "ota"],
        "status": "decided",
        "created": -45,
        "updated": -35,
        "body": """\
## Context

In March one firmware build silenced 140 sensors for two days. We shipped firmware to everyone at once, because that was all v1 could do.

## Options

1. **All at once, test harder.** Cheapest. Also what got us here.
2. **Random percentage rollout.** Better, but every rollout hits different gardens, so nobody can plan around it.
3. **Fixed rings:** our own sensors, then a fixed 10% slice, then everyone.

## Decision

Rings. Ring 0 is the 30 sensors in the office and in our own gardens. Ring 1 is a fixed 10% that includes pilot sites. Ring 2 is everyone. 48 hours per ring, auto-pause if missed readings go above 2%. Decided by @ravi 35 days ago, @theo agreed.

## Consequences

- A full rollout takes at least four days, fixes included, unless the on-call overrides it ([[on-call]]).
- Pilot gardens get new firmware early. @june warns them a day before.
- Built in [[firmware-ota]]. App releases are separate ([[release-process]]).
""",
    },
    {
        "slug": "d05-second-cell",
        "title": "D5: Qualify a second battery cell",
        "kind": "decision",
        "owner": "theo",
        "editor": "theo",
        "tags": ["decision", "battery", "supply"],
        "status": "open",
        "created": -18,
        "updated": -4,
        "body": """\
## Context

Every Fieldnote runs on one 2600 mAh lithium AA cell from one supplier (Cell A). In September their lead time went from 6 to 11 weeks. If they slip again, we miss launch.

The {{battery-life}} claim was measured on Cell A only.

## Options

| Option | For | Against |
|---|---|---|
| Stay single source | no work | one supplier holds our launch |
| Qualify Cell B (2500 mAh) | second source, better in the cold | 4% less capacity, three weeks of tests |
| Buy 6 months of Cell A now | simple | ties up cash, cells age on the shelf |

## Proposal

Qualify Cell B in parallel and launch on Cell A. With adaptive data rate both cells clear the claim with margin, and Cell B holds up better below 0 C. If Cell B passes cold and aging, any unit can ship with either. @theo proposes, @mara decides at battery sign-off.

## If accepted

- Two cells means two lines on the [[shipping-checklist]].
- Test plan and numbers live in [[battery-push]]; last walkthrough in [[m-battery-review]].

- [ ] Decide on Cell B @mara due:+12
""",
    },
    {
        "slug": "d06-android",
        "title": "D6: Drop Android 9",
        "kind": "decision",
        "owner": "sol",
        "editor": "sol",
        "tags": ["decision", "app", "android"],
        "status": "open",
        "created": -10,
        "updated": -7,
        "body": """\
## Context

The v2 first-run uses camera and Bluetooth APIs that are a mess on Android 9. 4% of active app users are on Android 9 or older, about 70 people, most of them in two pilot gardens on hand-me-down phones.

## Options

1. **Keep Android 9.** About two extra weeks, and a worse QR scanner for everyone.
2. **Set the v2 floor at {{min-android}}** and keep v1 working on old phones until spring.
3. **Drop it everywhere now.**

## Proposal

Option 2. iOS stays at {{min-ios}}. @sol proposes, @mara decides.

## If accepted

- [[onboarding-redesign]] gets simpler and ships on time.
- Support needs a "my phone is too old" macro, see the [[support-runbook]].
- The [[release-process]] QA shelf loses two old phones.

## Comments

@june is worried about the two pilot gardens. @arlo: "70 people is still 70 people." Fair. Hence keeping v1 alive until spring.

- [ ] List the affected pilot growers by name @june due:+2
""",
    },
    {
        "slug": "d07-coop-discount",
        "title": "D7: A discount for co-ops",
        "kind": "decision",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["decision", "pricing", "coop"],
        "status": "open",
        "created": -13,
        "updated": -9,
        "body": """\
## Context

The [[coop-pilot]] shows co-ops buy in bulk, share one gateway per site, and have one coordinator who answers for everyone. They also mostly run on grants, so price matters more than for a farm.

## Options

1. **No discount.** The price ({{price}}) is already low.
2. **{{coop-discount}} off sensors on orders of 50 or more.** The plan stays per garden.
3. **Free plan for co-ops**, full price hardware.

## Proposal

Option 2. It pays for itself through volume: 50 sensors in one shipment cost less to pack, and one coordinator means fewer tickets per sensor. @arlo proposes, @mara decides once the pilot renewal is clear.

## If accepted

- [[pricing]] gets a real co-op row.
- We need a simple way to check that a buyer is a co-op. A letter from their board is enough.
- First discussed in the [[m-pricing|pricing workshop]].

- [ ] Model margin at 50, 100 and 200 sensors @arlo due:-3
""",
    },
    {
        "slug": "d08-support-hours",
        "title": "D8: Support hours for launch",
        "kind": "decision",
        "owner": "june",
        "editor": "june",
        "tags": ["decision", "support"],
        "status": "decided",
        "created": -30,
        "updated": -16,
        "body": """\
## Context

In the pilot, support was "whoever sees it first". Replies took anywhere from 5 minutes to 3 days. For launch we need hours we can actually keep with one and a half people.

## Options

1. **Seven days a week, 8 to 20.** Needs a hire we can't afford before launch.
2. **Weekdays, office hours CET**, on-call only for outages.
3. **Email only**, 48-hour reply.

## Decision

Option 2: {{support-hours}}, by email at {{support-email}}. Outages page the on-call outside hours. Decided by @june with @mara 16 days ago. US growers get their replies in the morning; we revisit if US tickets go over 30%.

## Consequences

- Weekend tickets wait until Monday. The app says so on the help screen.
- The [[support-runbook]] and [[on-call]] page were updated to match.
- First look at the numbers in [[m-support-review]].
""",
    },
    # ------------------------------------------------------------------ meetings
    {
        "slug": "m-sync-1",
        "title": "Weekly sync, {date}",
        "kind": "meeting",
        "owner": "mara",
        "editor": "mara",
        "tags": ["meeting", "sync"],
        "status": "",
        "date": -21,
        "created": -21,
        "updated": -21,
        "body": """\
**Attendees:** @mara @theo @ines @ravi @sol @june @arlo

## Agenda

1. Launch scope
2. Battery numbers
3. Co-op pilot, week 3

## Notes

- Scope is locked for [[v2-launch]]. The web dashboard is out. Arlo is sad about it, noted.
- The sleep current fix is in ring 1. @ravi sees 18 uA on ring 0 units, down from 31.
- Cell B samples have been in the aging oven for three weeks. Theo wants it written up as a proper decision before anyone asks.
- Pilot: two gateways went offline over the weekend, both power. Otherwise quiet. See [[coop-pilot]].

## Decisions

- Scope lock stands.
- The sleep fix follows [[d04-rings]] like everything else. No shortcut to ring 2.

## Action items

- [x] Promote the sleep fix to ring 2 @ravi due:-19
- [x] Write up Cell B as a decision page @theo due:-18
""",
    },
    {
        "slug": "m-sync-2",
        "title": "Weekly sync, {date}",
        "kind": "meeting",
        "owner": "mara",
        "editor": "june",
        "tags": ["meeting", "sync"],
        "status": "",
        "date": -14,
        "created": -14,
        "updated": -13,
        "body": """\
**Attendees:** @mara @theo @ines @ravi @sol @june @arlo

## Agenda

1. Support hours
2. Android 9
3. Pricing workshop follow-up
4. Gateway installs

## Notes

- Support hours are decided ([[d08-support-hours]]). Macros start next week.
- @sol raised Android 9: the new QR scanner is painful there. He'll write it up as [[d06-android]].
- From the pricing workshop: co-op discount needs its own page. @arlo takes it ([[d07-coop-discount]]).
- Three pilot sites had gateway trouble, all power. @june wants a real install guide before launch, [[gateway-setup]]. Nobody has written it yet.

## Decisions

- None today. Two new decision pages coming.

Last week: [[m-sync-1]].

## Action items

- [x] Draft D6 @sol due:-10
- [x] Draft D7 @arlo due:-11
- [ ] Write the gateway install guide @theo due:-4
""",
    },
    {
        "slug": "m-sync-3",
        "title": "Weekly sync, {date}",
        "kind": "meeting",
        "owner": "mara",
        "editor": "mara",
        "tags": ["meeting", "sync"],
        "status": "",
        "date": -7,
        "created": -7,
        "updated": -7,
        "body": """\
**Attendees:** @mara @theo @ines @ravi @sol @june (@arlo out)

## Agenda

1. Battery
2. Onboarding prototype
3. Launch post

## Notes

- Battery: room temperature is fine, cold is not. 12.5 months projected at -10 C. Theo won't sign off before adaptive data rate is in ring 1. See [[battery-push]].
- Onboarding prototype with six growers: median 4 min 10 s to first reading. The waiting moment is the weak spot. [[onboarding-redesign]].
- Arlo left a launch post draft. It needs photos from real pilot gardens.
- [[d05-second-cell]] and [[d06-android]] are still open. Mara wants the list of affected Android growers before deciding D6.

## Decisions

- None. Both open decisions wait on data.

Last week: [[m-sync-2]].

## Action items

- [x] Adaptive data rate build to ring 0 @ravi due:-5
- [x] Share the prototype readout with the team @ines due:-6
- [ ] Photos from three pilot gardens @june due:-2
""",
    },
    {
        "slug": "m-sync-4",
        "title": "Weekly sync, {date}",
        "kind": "meeting",
        "owner": "mara",
        "editor": "mara",
        "tags": ["meeting", "sync"],
        "status": "",
        "date": 0,
        "created": 0,
        "updated": 0,
        "body": """\
**Attendees:** @mara @theo @ines @ravi @sol @june @arlo

## Agenda

1. Launch review follow-ups
2. D7
3. On-call for launch week

## Notes

- The launch review went fine, three yellow items: boxes, battery, co-op terms. See [[m-launch-review]].
- [[d07-coop-discount]]: Mara wants the pilot renewal answer first. Stays open.
- Launch week: @ravi and @sol double up on [[on-call]].
- @ines: the waiting state is the last design piece in [[onboarding-redesign]].
- Boxes: supplier still hasn't given a ship date. Theo calls them today.

## Decisions

- Launch date holds.

Last week: [[m-sync-3]].

## Action items

- [ ] Chase the box supplier for a ship date @theo due:+0
- [ ] Launch week on-call schedule @ravi due:+5
""",
    },
    {
        "slug": "m-pricing",
        "title": "Pricing workshop",
        "kind": "meeting",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["meeting", "pricing"],
        "status": "",
        "date": -18,
        "created": -18,
        "updated": -17,
        "body": """\
**Attendees:** @arlo @mara @june @ines

## Agenda

1. Co-op pricing
2. Trial length
3. How we show prices

## Notes

- The sensor stays at {{price}} ([[d02-price]]). Nobody wanted to reopen it.
- Co-ops: 8 of the pilot coordinators said the price per sensor is the blocker, not the plan.
- Arlo floated {{coop-discount}} off for orders of 50 or more. @june is fine with it as long as support load doesn't grow with it.
- Three free months with a kit stays ([[d03-plan]]). Only 2 of 40 interviewees mentioned it, but nobody minded it.
- EU shop shows VAT included. Ines wants the same price on the box and the site.

## Decisions

- Keep the sensor price and the trial.
- The co-op discount gets its own decision page: [[d07-coop-discount]].

## Action items

- [x] Update the pricing page @arlo due:-15
- [x] Ask five coordinators what they last spent on garden tools @june due:-12
""",
    },
    {
        "slug": "m-support-review",
        "title": "Support review",
        "kind": "meeting",
        "owner": "june",
        "editor": "june",
        "tags": ["meeting", "support"],
        "status": "",
        "date": -12,
        "created": -12,
        "updated": -12,
        "body": """\
**Attendees:** @june @ravi @sol @mara

## Agenda

1. Two weeks of pilot tickets
2. First look at the new hours

## Notes

86 tickets in two weeks.

| Topic | Tickets | Share |
|---|---|---|
| Setup and pairing | 27 | 31% |
| Gateway offline | 21 | 24% |
| Readings look wrong | 18 | 21% |
| Battery | 9 | 10% |
| Other | 11 | 13% |

- Median first reply is 3.5 hours inside {{support-hours}}. Before, it was "it depends".
- Setup is the biggest bucket. That is the whole case for [[onboarding-redesign]].
- "Readings look wrong" is mostly probes not pushed in to the line. The quick start card needs a bigger drawing.
- Battery tickets are all v1 units on old firmware.

## Decisions

- [[d08-support-hours]] stands. Look again after launch.

## Action items

- [x] Make the gateway check step one in the [[support-runbook]] @june due:-10
- [ ] Bigger depth drawing on the quick start card @ines due:+2
""",
    },
    {
        "slug": "m-pilot-retro",
        "title": "Co-op pilot, week 4 retro",
        "kind": "meeting",
        "owner": "june",
        "editor": "ines",
        "tags": ["meeting", "pilot", "coop"],
        "status": "",
        "date": -10,
        "created": -10,
        "updated": -9,
        "body": """\
**Attendees:** @june @ines @arlo @theo, plus Dana from the Elm Street site

## What went well

- 231 of {{pilot-units}} sensors report every day. The rest are in sheds or waiting on a gateway fix.
- Sites with proper gateway power had zero outages.
- Growers compare readings at the gate. Nobody planned for that, and it's great.

## What didn't

- Alert spam. One grower got 41 alerts in a week and turned them all off.
- Two probes cracked at the cable gland after the first frost. @theo took them to the lab.
- Coordinators can't see which plot is whose without asking.

## Changes

- One alert per bed per day, and a weekly digest for coordinators.
- Plot names on the site view.
- Pricing for co-ops goes to [[d07-coop-discount]].

Ines's notes from the visits are in [[n-garden-visits]]. Project page: [[coop-pilot]].

## Action items

- [x] Cap alerts at one per bed per day @sol due:-7
- [ ] Look at the cracked cable glands @theo due:+1
""",
    },
    {
        "slug": "m-design-crit",
        "title": "Onboarding design crit",
        "kind": "meeting",
        "owner": "ines",
        "editor": "ines",
        "tags": ["meeting", "design", "app"],
        "status": "",
        "date": -5,
        "created": -5,
        "updated": -5,
        "body": """\
**Attendees:** @ines @sol @arlo @june

## Agenda

First-run flows v3 for [[onboarding-redesign]], screen by screen.

## Notes

- QR scan first: everyone liked it. @sol: the camera permission prompt comes too early on iOS. Move it after the one-line explainer.
- "Push the probe in to the line": needs a real photo, not the illustration. Growers in the prototype pushed it half way.
- The first reading can take up to 90 seconds because of the sync window. A spinner won't do. Ideas in [[n-first-run]].
- @june: suggest names on the bed step ("Bed 1", "Tomatoes"). People skip empty fields.
- @arlo: the copy is too cute in two places. Back to [[brand-voice]].

## Decisions

- QR first, permissions after.
- No account creation until after the first reading.

## Action items

- [x] Cut the two cute lines @ines due:-4
- [ ] Move the camera permission after the explainer @sol due:+3
- [ ] Shoot probe photos in the lab @theo due:+4
""",
    },
    {
        "slug": "m-battery-review",
        "title": "Battery test review",
        "kind": "meeting",
        "owner": "theo",
        "editor": "theo",
        "tags": ["meeting", "battery"],
        "status": "",
        "date": -4,
        "created": -4,
        "updated": -4,
        "body": """\
**Attendees:** @theo @ravi @mara

## Agenda

1. Where the claim stands
2. Cell B
3. What if cold fails

## Notes

| Case | Projected life | Meets {{battery-life}}? |
|---|---|---|
| Cell A, 20 C | 14.0 months | yes, barely |
| Cell A, -10 C | 12.5 months | no |
| Cell A, -10 C, adaptive data rate | 14.8 months | yes |
| Cell B, -10 C, adaptive data rate | 15.2 months | yes |

- Adaptive data rate cuts energy per reading from 0.055 to 0.046 mAh on ring 0. Ring 1 is the real test, more gardens, worse links.
- Cell B dips less on the first pulse after a long sleep. That is why it wins in the cold despite 100 mAh less.
- Mara: if we have to lower the claim, we lower it now, not after launch.

## Decisions

- The claim stays if ring 1 holds for a week. Otherwise it drops to 12 months and [[v2-launch]] copy changes.
- [[d05-second-cell]] stays open until the aging readout.

Project: [[battery-push]].

## Action items

- [ ] Ring 1 adaptive data rate results to the team @ravi due:+7
- [ ] Draft fallback copy for a 12-month claim @arlo due:+6
""",
    },
    {
        "slug": "m-launch-review",
        "title": "Launch readiness review",
        "kind": "meeting",
        "owner": "mara",
        "editor": "mara",
        "tags": ["meeting", "launch", "v2"],
        "status": "",
        "date": -2,
        "created": -2,
        "updated": -2,
        "body": """\
**Attendees:** @mara @theo @ines @ravi @sol @june @arlo

## Agenda

Go through every area for [[v2-launch]] on {{launch-date}}. Green, yellow, or red, and why.

## Readiness

| Area | Owner | Status | Notes |
|---|---|---|---|
| Hardware batch | @theo | yellow | boxes late, no ship date |
| Battery claim | @theo | yellow | waiting on ring 1, see [[battery-push]] |
| Firmware | @ravi | green | rings working, two rollouts clean |
| App | @sol | green | new first-run behind a flag |
| Support | @june | green | macros half done |
| Pricing and launch posts | @arlo | yellow | [[d07-coop-discount]] open |

## Notes

- Nothing red. Three yellows, all with an owner and a date.
- The first 100 retail units get a full [[shipping-checklist]] dry run before anything goes out.
- Mara will not move the date for a yellow. A red, maybe.

## Decisions

- Date holds. Next review in one week. Go or no-go a week before launch.

## Action items

- [x] Update the launch milestones @mara due:-2
- [ ] Shipping checklist dry run on the first 100 units @theo due:+10
- [ ] Status page ready for launch day @ravi due:+12
""",
    },
    # ------------------------------------------------------------------ people
    {
        "slug": "mara",
        "title": "Mara Okafor",
        "kind": "person",
        "owner": "mara",
        "editor": "mara",
        "tags": ["people"],
        "status": "",
        "created": -420,
        "updated": -18,
        "body": """\
## Role

Founder and CEO. Ran a market garden for six years before Larkspur, which is where the first probe came from: a moisture meter taped to a stick.

## What I work on

- The [[v2-launch]], end to end. I own the date.
- Money: we have {{runway}} of runway. I update that number every month.
- Hiring, the co-op board, investors.
- Deciding the open decisions when they're ready, see [[how-we-work]].

## Ask me about

Why we chose a plan per garden ([[d03-plan]]), how the co-op deal came about, what we're not doing this year.

## How I like to work

Write it down first, then talk. I read everything at 7:00 and answer by 9:00. Thursday mornings are blocked for garden visits. If you need a decision from me, put it on a page with a proposal and tag me.

## Pages I own

{{query owned-by mara}}

## My open tasks

{{query tasks mara}}
""",
    },
    {
        "slug": "theo",
        "title": "Theo Lindqvist",
        "kind": "person",
        "owner": "theo",
        "editor": "theo",
        "tags": ["people", "hardware"],
        "status": "",
        "created": -415,
        "updated": -22,
        "body": """\
## Role

Hardware lead. Probe, enclosure, cells, radio, and the lab.

## What I work on

- The [[battery-push]], until the claim is signed off.
- Cell B, see [[d05-second-cell]].
- The first retail batch and the [[shipping-checklist]].

## Ask me about

Why LoRa ([[d01-lora]]), why the probe is that length, what happens to a cell at -20 C, anything on the bench. Read [[lab-rules]] before you ask to borrow the power analyzer.

## How I like to work

Mornings in the lab, afternoons for people. I write numbers in my lab notebook first and clean them up into the wiki later, so if a page looks a week behind, ask me. I prefer a ten-minute call over a long thread.

## Pages I own

{{query owned-by theo}}

## My open tasks

{{query tasks theo}}
""",
    },
    {
        "slug": "ines",
        "title": "Ines Duarte",
        "kind": "person",
        "owner": "ines",
        "editor": "ines",
        "tags": ["people", "design"],
        "status": "",
        "created": -380,
        "updated": -10,
        "body": """\
## Role

Design lead. The app, the box, the quick start card, and this wiki.

## What I work on

- The [[onboarding-redesign]]: five minutes from box to first reading.
- App copy and the [[brand-voice]].
- Keeping this wiki alive. If something is confusing, tell me, or fix it and tell me after. How it works: [[writing-here]].

## Ask me about

Why a screen looks the way it does, what growers said in the prototype tests, Figma access.

## How I like to work

I sketch on paper first and share early, ugly versions on purpose. Crits are Tuesdays at 14:00, open to anyone. I keep my own notes in this wiki too, under Notes, starting from [[n-inbox|my inbox]]. Those are messy and that's fine.

## Pages I own

{{query owned-by ines}}

## My open tasks

{{query tasks ines}}
""",
    },
    {
        "slug": "ravi",
        "title": "Ravi Menon",
        "kind": "person",
        "owner": "ravi",
        "editor": "ravi",
        "tags": ["people", "firmware"],
        "status": "",
        "created": -350,
        "updated": -15,
        "body": """\
## Role

Firmware. Everything that runs on the probe and the gateway, and the update server.

## What I work on

- Adaptive data rate for the [[battery-push]].
- Rollouts, as set in [[d04-rings]]. The machinery is [[firmware-ota]].
- The [[on-call]] rota. This week's on-call is {{oncall}}.
- Signing keys and access, see [[security-basics]].

## Ask me about

Why a probe missed readings, how much a radio packet costs in battery, how to read the gateway logs.

## How I like to work

Long quiet blocks. I check chat at 11:00 and 16:00. If something is on fire, page me, don't chat me. Firmware changes come with a short note on what they cost in microamps.

## Pages I own

{{query owned-by ravi}}

## My open tasks

{{query tasks ravi}}
""",
    },
    {
        "slug": "sol",
        "title": "Sol Park",
        "kind": "person",
        "owner": "sol",
        "editor": "sol",
        "tags": ["people", "app"],
        "status": "",
        "created": -300,
        "updated": -27,
        "body": """\
## Role

App engineer, iOS and Android. One codebase, two stores, a shelf of old phones.

## What I work on

- Building the new first-run for [[onboarding-redesign]].
- The [[release-process]] and the release train.
- Whether we keep Android 9, see [[d06-android]].

## Ask me about

Store review, crash reports, why the app needs Bluetooth permission (it doesn't for most growers, it's for co-op pairing).

## How I like to work

Small pull requests, reviewed the same day. I keep a running list of "things that will bite us" and bring one to every sync. Ping me with a screen recording, not a description.

## Pages I own

{{query owned-by sol}}

## My open tasks

{{query tasks sol}}
""",
    },
    {
        "slug": "june",
        "title": "June Halvorsen",
        "kind": "person",
        "owner": "june",
        "editor": "june",
        "tags": ["people", "support", "ops"],
        "status": "",
        "created": -280,
        "updated": -12,
        "body": """\
## Role

Ops and support. The help desk, the pilot gardens, shipping, the office, and most things nobody else owns.

## What I work on

- The [[coop-pilot]]: weekly check-ins with coordinators, gateway fixes, the renewal.
- The [[support-runbook]] and support hours ([[d08-support-hours]]).
- New hires, see [[onboarding]].

## Ask me about

Any customer by name, where a returned unit went, which pilot garden has the grumpy gateway, how to file an expense.

## How I like to work

I answer fast and I write things down. If you fixed something for a customer, tell me, or I'll fix it again. Monday mornings are for the support queue, don't book me.

## Pages I own

{{query owned-by june}}

## My open tasks

{{query tasks june}}
""",
    },
    {
        "slug": "arlo",
        "title": "Arlo Bennett",
        "kind": "person",
        "owner": "arlo",
        "editor": "arlo",
        "tags": ["people", "growth"],
        "status": "",
        "created": -200,
        "updated": -33,
        "body": """\
## Role

Growth. Pricing, the website, launch posts, and the interviews program.

## What I work on

- [[pricing]], and the co-op discount ([[d07-coop-discount]]).
- The launch post and press list for v2.
- Grower interviews, see the [[interviews-guide]].

## Ask me about

What growers actually said, what competitors charge, which forums small farmers read.

## How I like to work

Out of the office a lot, at markets and gardens. I write up every conversation the same day. Send me drafts early; I'd rather fix a rough one than polish a wrong one. Copy follows [[brand-voice]], even mine.

## Pages I own

{{query owned-by arlo}}

## My open tasks

{{query tasks arlo}}
""",
    },
    # ------------------------------------------------------------------ notes (Ines)
    {
        "slug": "n-shape-up",
        "title": "Reading: Shape Up",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["reading", "process"],
        "status": "",
        "created": -70,
        "updated": -22,
        "body": """\
Ryan Singer, Basecamp, 2019. Free to read online. Read most of it on the train back from a garden visit.

## What stuck

- **Appetite.** Start from how much time a thing is worth, not from an estimate. Fixed time, variable scope.
- **Shaping.** Before anyone builds, someone senior makes the work rough, solved, and bounded. Breadboards and fat marker sketches, not wireframes. Detailed enough to bet on, loose enough to leave room.
- **Bets, not backlogs.** A betting table picks pitches for the next cycle. Pitches that don't get picked aren't kept in a queue; if they matter, someone pitches them again.
- **Six-week cycles**, then a two-week cooldown.
- **Circuit breaker.** If it doesn't ship in the cycle, it doesn't get extended by default.
- **Hill charts.** Uphill is figuring out what to do, downhill is doing it. Much more honest than percent done.

## At Larkspur?

Six weeks is long for us, especially four weeks before launch. But appetite is exactly what worked on [[onboarding-redesign]]: "five minutes to first reading" was the shape, and scope moved around it.

Hill charts would help on [[battery-push]]. Theo is still uphill on the cold numbers and our status column says "in progress" like that means something.

Our Friday cleanup ([[how-we-work]]) is a tiny cooldown. After launch I want to try a real betting table: Mara, Theo, me. Compare with [[n-elegant-puzzle]].
""",
    },
    {
        "slug": "n-mom-test",
        "title": "Reading: The Mom Test",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["reading", "research"],
        "status": "",
        "created": -40,
        "updated": -30,
        "body": """\
Rob Fitzpatrick. Short book, about how to talk to customers so they can't lie to you, even by accident. The title: if you ask right, even your mom can't mislead you about your idea.

## The rules

1. Talk about their life, not your idea.
2. Ask about specifics in the past, not opinions about the future.
3. Talk less, listen more.

Other bits I underlined:

- Compliments are worthless. "That's so cool" means nothing.
- Look for commitment: their time, their reputation, their money. An intro to the co-op board beats ten "I'd buy it"s.
- Keep it casual. It doesn't need to be a meeting.

## Where I broke the rules

In the prototype sessions for [[onboarding-redesign]] I asked "would you use this every day?" Six out of six said yes. Useless. What worked was "show me how you checked your beds this morning". One grower literally walked me out and stuck her thumb in the soil.

## Do

- Fold this into Arlo's [[interviews-guide]]. It is already 80% there.
- Use the same rules on the next round of [[n-garden-visits]].
""",
    },
    {
        "slug": "n-elegant-puzzle",
        "title": "Reading: An Elegant Puzzle",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["reading", "management"],
        "status": "",
        "created": -55,
        "updated": -45,
        "body": """\
Will Larson, 2019. Subtitle: Systems of Engineering Management. Dense, lots of short essays, clearly written by someone who has run engineering at fast-growing companies. Half of it is about orgs ten times our size. Still worth it.

## What I kept

- **Team sizing.** Managers do best with roughly six to eight people. Below that they drift into coding, above that into being a router.
- **Four states of a team:** falling behind, treading water, repaying debt, innovating. Each one needs a different fix. Falling behind needs people; treading water needs less work in flight; repaying debt needs time; innovating needs slack you protect.
- **Migrations** are how you actually pay down tech debt, and the job isn't done until the last user is moved.
- **Systems thinking.** Stocks and flows, as a way to see why a team is stuck.

## For us

We're seven, so mostly this is about not making messes we'll pay for later.

- Ravi is treading water: on-call, rings, adaptive data rate, all at once. Less in flight, not more effort.
- [[firmware-ota]] was a migration done right: every sensor moved to dual-bank, nothing left behind.
- Pairs well with [[n-shape-up]] and our [[how-we-work]] page.
""",
    },
    {
        "slug": "n-first-run",
        "title": "Ideas: first-run moments",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["ideas", "design", "app"],
        "status": "",
        "created": -30,
        "updated": -6,
        "body": """\
Loose ideas for [[onboarding-redesign]]. Not a spec. Some of these are bad.

## The first reading is the moment

Everything before it is a chore. Everything after it is the product. So:

- Make the wait part of it. While we wait for the sync window, show what the number will mean: "Most beds sit between 20% and 40%. We'll tell you where yours is."
- Count down, don't spin. "Your probe is talking to the gateway... about a minute."
- When it lands, say it in words first, number second: "Bed 1 is fine. 31%."

## Smaller ones

- Pre-fill bed names. People skip empty fields (June said this in [[m-design-crit]] and she's right).
- A photo of the probe at the line, not an illustration.
- First-day digest email: one line per bed, sent at 18:00.
- Let them ask "is that good?" and answer for their plant. Tomatoes vs lettuce is a big difference.

## From the gardens

At Hollow Lane, people showed each other readings at the gate ([[n-garden-visits]]). Share-a-reading as part of first run? Maybe too much. Check the [[brand-voice]] before any of this gets copy.
""",
    },
    {
        "slug": "n-garden-visits",
        "title": "Notes from garden visits",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["research", "pilot", "coop"],
        "status": "",
        "created": -36,
        "updated": -10,
        "body": """\
Three of the {{pilot-sites}} in the [[coop-pilot]], visited over two weeks. Mostly listened, per [[n-mom-test]].

## Elm Street Allotments

Dana coordinates, 28 plots. The gateway was on an extension cord shared with a kettle, which explains the outages.

> "I don't need to know every bed. I need to know which three people to call."

That's the coordinator digest, right there.

## Hollow Lane Community Garden

Older growers, lots of hand-me-down Android phones (see [[d06-android]]). Nobody opens the app daily. They check it at the gate when they arrive.

> "I walk the beds with my thumb. This is a better thumb."

They compare readings with each other. Social, not personal.

## Brook Farm Plots

One market grower renting six plots, 30 sensors. The power user. Wants per-bed watering times and is annoyed we don't control valves.

> "Tell me tonight, not at 3 in the morning."

## Patterns

- Nobody wants alerts at night.
- Coordinators and growers want different apps. Same data.
- Seeing the probe builds trust. Bright flag stays. Ideas for first run in [[n-first-run]].
""",
    },
    {
        "slug": "n-inbox",
        "title": "Inbox",
        "kind": "note",
        "owner": "ines",
        "editor": "ines",
        "tags": ["inbox"],
        "status": "",
        "created": -90,
        "updated": -1,
        "body": """\
Scratch. Sort on Fridays.

- Is the coordinator digest a design problem or an eng one? Probably design. Talk to June about [[coop-pilot]] first.
- Co-op people say plot, farmers say bed. The app says bed. Glossary?
- Probe flag color that changes with moisture? Theo will say power. Ask anyway.
- [[expenses]] page hasn't been touched since last year and nobody follows the hotel cap. Poke Mara.
- Waiting state: try a soil cross-section animation, fill level rises? Too cute? See [[n-first-run]].
- Every stale page is a page someone stopped trusting ([[writing-here]] needs a line about that).
- German copy is 30% longer. Design for German first next time.

- [ ] Send Dana the digest mockup @ines due:-6
- [ ] Ask about a moisture-colored probe flag @ines due:+10
""",
    },
]
