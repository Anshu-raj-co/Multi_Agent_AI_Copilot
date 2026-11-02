# The story of Multi-Agent Copilot

*A plain-language story of the whole project, for anyone. No technical background needed.*

**Authors:** Anshu Raj and Garima Pandey

If you want the technical details instead, read the [A-to-Z guide](PROJECT_A_TO_Z.md).

---

## 1. The problem in one picture

Imagine a company with a fleet of delivery trucks. Every truck keeps sending little updates: where it is, how fast it is
going, how much fuel it has. In the office, a dispatcher watches all of this on a screen.

Now imagine the screen shows a calm green light that says "everything is fine". The truck's numbers are on the screen,
neatly laid out. But they have not changed for a while. The truck stopped sending updates, and the screen keeps showing
the last ones it received.

That is like being handed yesterday's newspaper and being told it is today's. It looks real. It is printed properly. But
the news is old. We call this **stale data**: information that looks current but is actually out of date.

Why is that dangerous? Because the dispatcher trusts the green light. They may send help to the wrong place, or miss a
truck that has broken down. The most dangerous problems are not the loud ones. They are the quiet ones, where everything
*looks* fine.

## 2. The idea: break one small thing, on purpose, safely

How do you find out whether a system can be fooled like this? You test it. You switch off one small part on purpose, for
a few seconds, and watch what happens. Then you switch it back on and check that everything really recovers.

This sounds risky, so we do it the careful way. A real person has to say yes first. The test is short. And there is
always a way to stop it instantly.

This practice has a name: **chaos engineering**, which means testing a system by causing small, controlled failures on
purpose, so you find weak spots before a real failure does.

## 3. The system we test

We do not test a toy. We test a real, free, publicly shared fleet-management system, built by an open community of
car-software developers. On our computer it runs as eight small programs that work together. Each one lives in its own
**container**, which is like a small apartment where one program lives, with its own door and its own things.

Here is how a truck update travels, in four steps. First, a stand-in for a real truck plays back recorded readings from a
real vehicle. Second, a "radio operator" program on the truck side packs each reading into a message and stamps it with
the time it was made. Third, the message travels through a relay to an office clerk, who files it in a filing cabinet
that sorts everything by time. Fourth, when the dispatcher's screen asks "what is the latest?", an answer desk looks in
the cabinet and replies.

For the curious, the eight programs are called csv-provider, databroker, fms-forwarder, fms-zenoh-router, fms-consumer,
influxDB, fms-server and grafana.

The answer desk works like a waiter in a restaurant. You ask the waiter for something, the waiter goes to the kitchen and
brings back an answer. In computing, this kind of waiter is called an **API**. When the waiter says "all good, here you
go!", computers write that as **HTTP 200**. And here is the catch we found: the waiter keeps saying "all good!" even when
the kitchen has nothing fresh, and serves the old plate again.

## 4. Meet the team of five

Our project is a small team. Four members are parts of the computer program, and one is always a human.

- **The Monitor (the watcher)** checks that the trucks' updates are fresh before anything happens.
- **The Planner (the suggester)** looks at past tests and suggests three possible tests, ranked from most useful to least.
- **The Human gate (the person who says yes)** is a real person, who reads the suggestion and types their own name to
  approve it. Nothing happens without this.
- **The Safety Executor (the careful hands)** runs the approved test, watches the clock, undoes the change, and checks
  that things really recovered.
- **The Analyst (the explainer)** writes a short report and gives the test a score.

Two members, the Planner and the Analyst, may ask an **AI helper** for their wording. This is a text-writing AI that
runs on the same computer, so nothing leaves the machine. The Monitor and the Safety Executor never use the AI. That is
on purpose: the part that stops a problem must never depend on a guess.

What if the AI helper is switched off, slow, or wrong? Then the system quietly uses simple, fixed rules instead, and
says so in its report. Every AI answer is checked against what was actually recorded. If it does not match, it is
thrown away.

## 5. One real test, told as a story

This is a real test, recorded on 2 November 2026.

First, the watcher looked at the trucks' updates six times in a row. All six were fresh, and the oldest was a little
under one and a half seconds old (1.373 seconds). Healthy. It handed over to the suggester.

The suggester ranked three possible tests: switch off the filing cabinet for a moment, restart the truck's radio
operator, or freeze the radio operator. The AI helper was switched off for this test, so the suggester used its fixed
rules.

Then a real person, Anshu, read the options, chose "freeze the radio operator" (ranked third), and typed their name to
approve it. The system wrote down exactly who approved what, and when.

The careful hands froze the radio operator for 25 seconds. From that moment, no new truck updates were made.

And the dispatcher's screen? It kept saying "all good!" on every single check. The program asked twice a second, and
37 times it got an "all good" answer while the data was stuck. By the end, the newest truck update on the screen was
almost 25 seconds old (24.863 seconds).

The system noticed. 5.132 seconds after the freeze began, it flagged the data as stale, even though the screen still
said everything was fine.

When the 25 seconds were up, it undid the change and unfroze the radio operator. Then it checked, in a separate way,
that the radio operator really was running again. But that alone was not enough to call it "recovered". It waited until
three fresh truck updates arrived in a row, each one newer than the last. The first fresh update came 1.13 seconds after
the undo. The third one, which confirmed recovery, came 2.81 seconds after the undo.

Finally, the explainer wrote its report. It gave this test a score of 45.1 out of 100 and listed 9 findings across all
51 recorded tests, 2 of them about this test. The record also shows a gap of about 25 seconds (25.531 seconds) in the stored truck
updates: none were made while the radio operator was frozen, and nothing fills the gap afterwards.

## 6. What you see on the screen

The project has its own live screen, a dashboard, that you open in a web browser.

At the top is a **3D map of the whole system**, which you can turn with your mouse. It shows three layers: the eight
programs and how they connect, the team of five, and the safety layer. When everything is healthy, the map is green and
little dots flow along the lines, like parcels on a conveyor belt. During a test, the frozen part turns orange or red,
the dots stop, and a red label says "HTTP 200 but STALE": the screen says "all good" while the data is old. If the
dashboard loses contact, it says "no live data" and nothing moves. It never pretends.

Below that is a **clock showing how old the data is**, the answer the screen is giving, and a chart of the last minute.
Then come **the three tests to choose from**, each on one line, with an approve button that needs your name. Last, there
is **a log of who did what**: each team member's step, in order, with the name of the person who approved.

## 7. The safety rules, in plain words

- **Only pre-approved targets.** The system has a short list of parts it may touch. It checks the exact name and a
  label on each one. Anything else is refused.
- **One test at a time.** A second test cannot start while one is running, even from another window.
- **Never longer than 30 seconds.** Every test is capped, including a small grace period.
- **An automatic timer.** A separate timer watches the clock and undoes the change on its own if anything goes wrong.
- **A big red stop button.** Like the emergency stop on a factory machine. It works from the screen, from a typed
  command, or as a separate small helper that works even if the main program has crashed.
- **The undo is double-checked.** First the system checks that the part is really running again. Then it checks,
  separately, that fresh truck updates are arriving. A "fine" from the screen is never accepted as proof.

If the undo cannot be confirmed, the system locks itself. No new test can start until a person has looked at it and
unlocked it, and that unlock is written down.

## 8. What it gives you at the end

After each test you get three things. First, a **saved record** of everything that happened, second by second, kept on
the computer. Second, a **resilience score out of 100**, a single number for how well the system coped. It looks at how
fast the problem was noticed, how fast it recovered, how much data was lost, and whether anything else was disturbed.
Third, a **plain list of findings**, most serious first.

## 9. What we found

These results come only from the saved test records. We recorded 19 tests where the radio operator was frozen.

- **The screen said "all fine" while the data was frozen, every time we could measure it.** In all 18 of those tests
  that recorded the screen's answers, 100% of the checks during the freeze said "all good".
- **We noticed quickly.** In the 13 tests that ran their full planned time, the system flagged stale data between 4.768
  and 5.332 seconds after the freeze began.
- **Recovery was confirmed a few seconds after the undo.** In 18 of the 19 tests, recovery was confirmed between 2.117
  and 3.73 seconds after the undo. The 19th was a deliberate crash test: we forcibly closed the program in the middle of a
  test. When it restarted, it undid the freeze by itself and locked itself until a person checked, exactly as designed.
- **Some data is simply lost.** While the part is frozen, those truck updates are never made or stored. Nothing catches
  up afterwards.

## 10. The honest limits

- **It does not fix anything.** It tests, undoes its own change, and reports. Fixing is up to people.
- **It is not a robot that runs on its own.** A person must approve every test. The team is a short, fixed sequence of
  steps that we wrote ourselves, not a big ready-made toolkit for AI teams.
- **It was tested on one computer, with one truck, and a small number of tests.** That is enough to show the problem
  clearly, but it is not a large study.
- **The AI helper adds little so far.** In the recorded checks, only 1 of 7 of its explanations matched the evidence.
  The fixed rules do the heavy lifting.
- **It is not meant for real vehicles yet.** It only ever touches a practice copy of the system on our own computer.

## 11. What could come next

- Building the team on a more advanced, ready-made toolkit for AI teams.
- Going one step further and suggesting or even applying fixes, with a person still in charge.
- Linking a failure to the exact change in the software that caused it, so developers know where to look.

## 12. Project history

Multi-Agent Copilot extends the ResiliencePilot SDV project (Bosch Hackathon 2026, original repository:
https://github.com/Anshu-raj-co/ResiliencePilot); the multi-agent team layer, human approval gate, session trace, team
API, dashboard panels and the System in 3D view were added for this project.

---

## In one minute

1. A fleet screen can say "everything is fine" while the truck data on it is old and frozen.
2. Our program proves this by freezing one small part for a few seconds, only after a named person says yes.
3. It notices the old data in about five seconds, even though the screen still says "all fine".
4. It undoes the change and only calls it fixed when three fresh updates arrive in a row.
5. It writes down everything, gives a score out of 100, and lists what it found, honestly.

---

> **If you want to try it**
>
> You need a computer with Docker Desktop, Python 3.13 and Git. The README's "Quick start" section has the exact steps:
> start the practice system with `./scripts/stack-up.sh`, then open the dashboard with `mcop serve` and visit
> http://127.0.0.1:8765/. See [README.md](../README.md) and the [A-to-Z guide](PROJECT_A_TO_Z.md).
