# Player-Value Accounting and Double-Counting Audit (Phase 6 §12)

How value flows through a PLL possession, which player actions receive value,
and why one point of team scoring never becomes more than one point of player
value.

Every scenario below is executed as a test in
`tests/test_player_value.py::TestAccountingNoDoubleCounting`, so this document
and the code cannot drift apart silently.

---

## 1. The accounting identity

The framework is **residual**, not **allocative**. This distinction is what
makes the whole thing safe, and it is worth being precise about.

An *allocative* system starts from a team's 163 points and divides them among
players. Such a system must double-count if two players are credited for the
same goal, and its components must sum to the team total.

This framework does not do that. Each component is:

```
component = (what the player produced on his own recorded opportunities)
          − (what a league-average player would have produced on the same
             opportunities)
```

Nothing is divided up. Team points are never partitioned. Consequently:

```
Σ over all players of every component = 0, exactly.
```

Verified: shooting `−0.0000000000`, turnover `+0.0000000000`, faceoff
`+0.0000000000`, caused-turnover `+0.0000000000`, goalie `+0.0000000000`,
total `−0.0000000000` (validation checks 14–16).

The risk in a residual system is therefore **not** "two players share one
goal". It is **"one player's single action is valued through two different
components"**. The audit below is organised around that risk.

## 2. The disjointness rule

Two components can only double-count if they draw on the **same opportunity**.
So every component is defined over a distinct opportunity set:

| Component | Opportunity set | Baseline |
|---|---|---|
| `shooting_value` | the player's shot **attempts** | league expected points for that shot class |
| `turnover_value` | the player's **touches** | position-group turnovers per touch |
| `faceoff_value` | the player's **faceoffs** | league faceoff win probability (0.49656) |
| `caused_turnover_value` | the player's **games played** | position-group caused turnovers per game |
| `goalie_value` | **shots on goal faced** | league expected points per shot on goal |

No two share a denominator. A shot attempt is never also counted as a touch
opportunity for turnover purposes; a faceoff is never also a shot.

Two components are **deferred precisely because they would break this rule** —
see §4 and §5.

## 3. Value flow through a possession

```
   possession begins (faceoff win / turnover / defensive ground ball)
        │
        │  ← faceoff_value, if it began on a draw and only for wins above expectation
        ▼
   offensive opportunities: touches, passes
        │
        │  ← turnover_value, if the ball is lost above the rate the role implies
        ▼
   shot attempt(s)
        │
        │  ← shooting_value on each attempt (finishing only, never creation)
        │  ← goalie_value on each shot ON GOAL, to the opposing keeper
        ▼
   possession ends: goal / turnover / shot-clock / defensive recovery
        │
        │  ← caused_turnover_value, to the defender officially credited
        ▼
   team points recorded
```

Nothing in that chain credits a player for *having* the possession. That is
deliberate: possession value is a team quantity, and the feed cannot say who
was on the field for it (§6).

## 4. Scenario audit

### A. Missed shot

| Player | Component | Value |
|---|---|---|
| Shooter | `shooting_value` | `0 − 0.29300 = −0.293` |
| Anyone else | — | none |

The possession continues, so nothing else fires. Note the contrast with
Lacrosse Reference, where a missed shot is the single most *positive* play
(+0.19) because the window measures what happens next and you still have the
ball. Here the shooter is charged for a chance he did not convert. **Both are
defensible; they answer different questions.** This framework asks about
finishing, so the miss is a cost.

### B. One-point goal

| Player | Component | Value |
|---|---|---|
| Shooter | `shooting_value` | `1 − 0.29300 = +0.707` |
| Opposing goalie | `goalie_value` | `0.46120 − 1 = −0.539` |

Total player value created on the scoring team: **+0.707 for one point of team
scoring.** Less than one point, never more.

The goalie's charge is on the other team. It does not cancel the shooter's
credit within a team and it is not meant to — it is the same event scored
against two different opportunity sets on opposite sides of the ball, exactly
like an interception costing a quarterback and crediting a defensive back.
League-wide the two sides net to zero because both components sum to zero
independently.

### C. Two-point goal

| Player | Component | Value |
|---|---|---|
| Shooter | `shooting_value` | `2 − 0.26866 = +1.731` |
| Opposing goalie | `goalie_value` | `0.48161 − 2 = −1.518` |

**One goal, two points.** The goal count increments by one; the point value is
two. The expectation charged is a two-point-sized expectation (`P(goal) × 2`),
so a player is not rewarded merely for shooting from distance — in 2026 the
league two-point attempt was worth 0.269 points against 0.293 for a one-point
attempt, so a two-point attempt starts marginally *behind*.

### D. Turnover

| Player | Component | Value |
|---|---|---|
| Committer | `turnover_value` | `−(1 − expected) × 0.20046` |

**The double-counting trap here is the one the brief warns about.** A turnover
ends the offensive possession, so it is tempting to charge the player the
possession's full expected value (0.271) *and* the turnover's transition cost
(0.200). That would charge the same lost opportunity twice.

It does not happen here, because `shooting_value` never credits or charges
possession value in the first place — it only prices conversion on attempts
that were actually taken. There is no possession-value term anywhere in the
framework for a turnover charge to duplicate.

Worked composite: a possession with two missed shots ending in a turnover by
the same player:

```
shooting_value  = 0 − 2 × 0.29300 = −0.586      (two attempts, priced once each)
turnover_value  = −1 × 0.20046    = −0.200      (one turnover, priced once)
total           = −0.786
```

Two shot events and one turnover event, three prices, no event priced twice.

### E. Caused turnover followed by a ground-ball recovery

This is the scenario that killed the ground-ball component.

| Player | Component | Value |
|---|---|---|
| Defender who caused it | `caused_turnover_value` | `+(1 − expected) × 0.20046` |
| Same defender, scooping the loose ball | `ground_ball_value` | **deferred — nothing** |
| Opponent who lost it | `turnover_value` | `−(1 − expected) × 0.20046` |

A caused turnover and the ground ball that follows it are **one change of
possession described twice**. Paying both would value it twice. Ground-ball
value is deferred, so the defender is paid once.

The committer's charge and the causer's credit are equal and opposite, so the
pair nets to zero league-wide. They fall on different teams, which is correct:
one player lost the ball and another took it.

### F. Faceoff win

| Player | Component | Value |
|---|---|---|
| Faceoff winner | `faceoff_value` | `(wins − faceoffs × 0.49656) × 0.34643` |
| Same player, scooping the draw | `ground_ball_value` | **deferred — nothing** |

Two safeguards operate here.

**The counterfactual.** A win is not worth a full possession. The alternative
to this player winning is a *league-average faceoff man* winning at 49.656%,
not the team forfeiting the ball. A specialist who wins exactly at the league
rate scores exactly zero.

**The scrum ground ball.** 1,095 of the season's 3,091 ground balls immediately
follow a faceoff. **99.7% go to the faceoff-winning team and 61.5% to the
faceoff winner himself.** A per-ground-ball credit would therefore pay the FOGO
a second time for the same draw, on 673 occasions. Faceoff specialists average
7.11 ground balls per game — more than double any other position — almost
entirely through this mechanism. This alone is decisive.

The coefficient is `2 × 0.17321`, not `0.17321`: converting a loss into a win
moves the value from the opponent to you, so the swing is twice the event
value.

### G. Goalie save

| Player | Component | Value |
|---|---|---|
| Goalie | `goalie_value` | `+0.46120` (one-point shot on goal) |
| Shooter | `shooting_value` | `−0.29300` |

Note the asymmetry in magnitude: the goalie's baseline (0.461 per shot **on
goal**) is larger than the shooter's (0.293 per **attempt**), because shots on
goal convert at a higher rate than all attempts. Both are correct against their
own opportunity sets. Goalies are not charged for shots that missed the cage —
they did not have to do anything about those.

### H. Assisted goal

| Player | Component | Value |
|---|---|---|
| Shooter | `shooting_value` | `1 − 0.29300 = +0.707` |
| Assister | `assist_value` | **deferred — nothing** |

**One point of team scoring yields +0.707 of player value, not +1.2 split two
ways and not +0.707 twice.**

Official assists are reliable — 560 season-wide, reconciling exactly with team
totals in all 100 team-games — and are carried as a descriptive count. They are
not *valued*, because the points from an assisted goal are already fully priced
in the shooter's component. Adding an independent assist credit would create
two players' worth of value from one goal.

Splitting credit between shooter and assister (say 70/30) is a defensible
alternative, but it changes what `shooting_value` means — it would stop being
"finishing versus expectation" and become "finishing versus expectation, minus
a share for whoever passed". That is a decision for the phase that needs it,
not a default to slip in here.

The feed's `shotAssistId` is used **nowhere** in this layer. It is a pre-shot
pass indicator, not a confirmed assist, and an unpopulated value is not a
negative assertion. Validation check 23 greps the value SQL to enforce this.

## 5. Summary: what is deliberately NOT valued, and why

| Not valued | Reason |
|---|---|
| Ground balls | No opportunity denominator; contexts statistically inseparable; 35% of them overlap faceoff value (scenarios E, F) |
| Assists | Already priced in the shooter's component (scenario H) |
| Possession itself | Cannot be attributed to a player — no lineup data (§6) |
| Penalties | Coefficient estimated (−0.417) and published, but no component added in Phase 6 |
| Shot creation | Not separable from finishing in this feed |
| Everything defence does that is not a caused turnover | Leaves no trace in the feed |

## 6. The attribution boundary

No player receives value from an opportunity he cannot be individually tied to.

The PLL feed carries **no lineup, substitution or on-field data of any kind**.
Team possessions while a player was on the field are therefore not computable,
and nothing in Phase 6 is denominated in possessions. Validation check 22
asserts that no component column contains `per_possession`, and check 13
asserts that a player with zero opportunities of a class carries NULL for that
component rather than a zero score.

`play_shares` (appearances in the event log) is published as a **usage proxy**
only — it is Lacrosse Reference's own definition, and it is not playing time
and not possessions.

## 7. Known accounting limitations

1. **~19% of league turnovers are charged to nobody.** Player-attributed
   turnovers total 1,369 against an official team total of 1,699, because the
   feed's turnover descriptions name only a team. The baseline is computed from
   the same player-level data so the residual is internally consistent, but
   every player's turnover load is understated in absolute terms.
2. **The defensive component is one act wide.** Caused turnovers only.
3. **Games played is a crude exposure measure** for the defensive component —
   no minutes exist in the feed.
4. **Goalie value is not shot-quality adjusted.** No shot location, distance or
   defender data exists, so a keeper behind a defence that concedes close-range
   shots is charged for it.
5. **Cross-position totals are not comparable.** A goalie faces 150–330 shots on
   goal; an attackman takes ~80 shots. The opportunity bases differ by a factor
   of three or more, so `total_player_value` spreads much wider for goalies.
   This is a property of the value unit, not a bug, and it is exactly why
   Phase 6 stops short of an award ranking.
