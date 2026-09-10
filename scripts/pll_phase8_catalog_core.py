"""
Phase 8: the canonical metric catalog -- schema, helpers and shared text.

This module holds the row constructor and every string that is reused across
many catalog rows. The rows themselves live in two sibling modules so neither
file becomes unreviewable:

    pll_phase8_catalog_team.py     team-level metrics
    pll_phase8_catalog_player.py   player-level metrics + rejected concepts

`pll_metric_catalog.py` assembles them and is the single import point.

Why a catalog at all
--------------------
Phases 5, 6 and 7 each published their own metric-definition CSV in their own
schema. Three schemas cannot be queried together, so nobody could answer "what
is every published 2026 statistic, and is it trustworthy?" without reading three
files and reconciling them by hand. The Phase 8 catalog is one schema over all
three phases plus Phase 8's own additions. It supersedes NONE of them: the
earlier files stay on disk, byte-identical, and `phase_origin` points back at
the phase that defined each metric.

Publication status
------------------
CORE         trustworthy enough to lead with. Well-defined denominator, source
             reconciled, sample adequate for the claim the metric makes.
CONTEXTUAL   publishable, but only alongside something else -- a denominator, a
             sample size, a companion metric, or a stated caveat. Most rate
             metrics at 2026 sample sizes land here.
EXPERIMENTAL defensible construction, unvalidated interpretation. Publish with
             the construction visible; do not build on it.
DIAGNOSTIC   exists to expose a disagreement, a coverage gap or a model
             assumption. Never a statistic about a team or a player.
DEFERRED     wanted, not currently supportable; the missing input is named.
UNSUPPORTED  cannot be built from this feed at all, and would mislead if faked.

A metric is NOT labelled CORE merely because it computes.

Freeze classification (Phase 8 s23)
-----------------------------------
FREEZE                  definition can be applied unchanged to 2022-2025.
FREEZE_WITH_CAVEAT      definition is stable; a stated property of the metric
                        must travel with it into every season.
REVISE_BEFORE_HISTORICAL definition works for 2026 but a multi-season pool
                        changes what the right definition is.
DO_NOT_USE              do not carry backward; do not publish.
"""

CATALOG_COLUMNS = [
    "metric_name",
    "display_name",
    "entity_level",
    "category",
    "unit",
    "numerator_definition",
    "denominator_definition",
    "formula",
    "source",
    "interpretation",
    "higher_is_better",
    "eligibility_rule",
    "minimum_sample_reason",
    "reliability_status",
    "cross_position_comparable",
    "official_or_reconstructed",
    "publication_status",
    "known_limitations",
    "phase_origin",
    "redundancy_class",
    "freeze_classification",
]

# --------------------------------------------------------------------------
# Shared limitation text. Written once so a caveat cannot drift between the
# rows that share it.
# --------------------------------------------------------------------------
L_NOT_OPP_ADJ = (
    "Not opponent-adjusted: the value reflects the schedule faced. No "
    "strength-of-schedule adjustment exists anywhere in this project."
)
L_SMALL_LEAGUE = (
    "8 teams over 12-13 games. The Phase 5 null model showed that randomly "
    "resampling possessions alone moves 8-12 total rank places, so small rank "
    "gaps in an 8-team table are not meaningful."
)
L_POSS_SUBSET = (
    "Per-possession LEVELS are subset-dependent: 0.271 points per possession on "
    "the full possession set against 0.326 on the non-ambiguous subset are "
    "answers to different questions, not a better and a worse estimate of one. "
    "Rankings are insensitive (Phase 5 null model, p 0.135-0.922); levels are not."
)
L_OFFICIAL_TO = (
    "Official box-score numerator. 19 games carry unresolved turnover residuals "
    "from Phase 4.25; the per-team play-by-play-minus-official residual is on the "
    "team-game row and season aggregates are affected by well under 1%."
)
L_OFFICIAL_GB = (
    "Official box-score numerator. 16 games carry unresolved ground-ball "
    "residuals from Phase 4.25."
)
L_MANUP = (
    "PLL's man-up tag lands on GOALS ONLY -- all 90 tagged events in 2026 are "
    "valid goals -- so man-up shot volume must come from the official box score "
    "and no man-up POSSESSION exists. The denominator is the extra-man "
    "opportunity, never a possession. No penalty-clock state is reconstructed."
)
L_TWO_POINT_THIN = (
    "536 two-point attempts league-wide across 8 teams. A team's two-point "
    "conversion rests on 38-83 attempts, which is thin enough that team-level "
    "differences are dominated by sampling noise -- see "
    "two_point_audit_2026.csv, where the standard error is on every row."
)
L_TWO_POINT_NOT_ID = (
    "INDIVIDUAL TWO-POINT ABILITY IS NOT IDENTIFIABLE IN 2026. The observed "
    "between-player variance (0.0234) is smaller than binomial noise alone "
    "predicts (0.0276); the estimated prior strength is capped at 1e6 and every "
    "shrunk rate equals the league mean. Production may be described; ability "
    "may not be ranked."
)
L_TURNOVER_ATTRIB = (
    "About 19% of league turnovers are attributed to NO player: player sums give "
    "1,369 against an official team total of 1,699, because the feed's turnover "
    "descriptions name only a team. Every player-level turnover count and every "
    "usage measure built on turnovers is understated by an unknown, non-uniform "
    "amount."
)
L_XPOS_C = (
    "NOT cross-position comparable (Phase 7 class C). A shared unit is not a "
    "shared scale: the opportunity bases differ by 6.6x in observed spread "
    "(goalie sd 9.59 against defensive-field 1.46). Partition by position before "
    "reading."
)
L_DEF_PARTIAL = (
    "PARTIAL by construction. It measures caused turnovers above the position "
    "group's per-game average and NOTHING ELSE. Off-ball defence, help "
    "positioning, matchup difficulty, forcing a bad shot instead of a turnover, "
    "shot suppression, sliding, recovery and communication leave no trace in this "
    "feed. A value of 0.0 does NOT mean 'an average defender'. The denominator is "
    "games played, because the feed has no minutes, shifts or lineups."
)
L_GOALIE_NO_SQ = (
    "No shot-quality adjustment is possible: shot events in this feed carry no "
    "location, no distance and no defender, verified across all 51 raw games. A "
    "keeper behind a defence that concedes point-blank looks worse; a keeper "
    "behind one that forces long shots looks better."
)
L_SHOOTING_NOISE = (
    "Weakly identified at 2026 samples: the median shooter took 9 attempts, only "
    "13 of 192 reach reliability 0.5, and the null-standardized spread of "
    "shooting value is 1.067 against 1.0 under pure chance -- implying roughly "
    "12% of the observed between-player variance is skill."
)
L_USAGE_NOT_POSS = (
    "This is NOT the share of team possessions the player was on the field for. "
    "The PLL feed carries no lineup, substitution, shift or minutes data of any "
    "kind. Numerator and denominator are both counted individual actions."
)
L_SPAN_NOT_TOP = (
    "A possession SPAN is the interval from a possession's first logged event to "
    "its last. It is NOT time of possession: it recovers a median 75% of PLL's "
    "official figure with a 0.54-1.00 range and r=0.58, because it excludes "
    "transition, clearing and dead-ball time. Use the official figure."
)
L_ASSIST_UNVALUED = (
    "DESCRIPTIVE ONLY, and deliberately unvalued. The points from an assisted "
    "goal are already fully priced in the shooter's shooting value; an "
    "independent assist credit would create two players' worth of value from one "
    "goal. Official assists are reliable (exact in 100/100 team-games); the "
    "feed's shotAssistId is a pre-shot pass indicator and is used nowhere."
)
L_GB_UNVALUED = (
    "DESCRIPTIVE ONLY, and deliberately unvalued. 1,095 of 3,091 ground balls "
    "immediately follow a faceoff, 99.7% go to the faceoff-winning team and 61.5% "
    "to the winner himself, so a per-ground-ball credit would pay the same player "
    "twice for one change of possession 673 times. There is also no ground-ball "
    "OPPORTUNITY denominator in the feed."
)


def M(name, display, level, category, unit, num, den, formula, source, interp,
      hib, pub, phase, limits,
      eligibility="all rows in scope",
      min_reason="not_applicable: no minimum applies",
      reliability="not_applicable",
      xpos="not_applicable",
      official="reconstructed",
      redundancy="DISTINCT",
      freeze="FREEZE"):
    """Build one catalog row.

    `hib` is TRUE / FALSE / 'neither' -- 'neither' for metrics where a
    direction is a style choice rather than a quality (two-point attempt rate,
    pace) or where the column is a diagnostic.
    """
    return {
        "metric_name": name,
        "display_name": display,
        "entity_level": level,
        "category": category,
        "unit": unit,
        "numerator_definition": num,
        "denominator_definition": den,
        "formula": formula,
        "source": source,
        "interpretation": interp,
        "higher_is_better": hib,
        "eligibility_rule": eligibility,
        "minimum_sample_reason": min_reason,
        "reliability_status": reliability,
        "cross_position_comparable": xpos,
        "official_or_reconstructed": official,
        "publication_status": pub,
        "known_limitations": limits,
        "phase_origin": phase,
        "redundancy_class": redundancy,
        "freeze_classification": freeze,
    }
