-- Phase 7: usage-adjusted value, kept in its own table.
--
-- The transformation is NOT hidden inside the wide player table: every input,
-- the expectation, the residual and the uncertainty around it are here side by
-- side so the arithmetic can be followed by eye.
--
-- ===========================================================================
-- THREE DIFFERENT QUESTIONS, THREE DIFFERENT COLUMNS
-- ===========================================================================
--
-- 1. "What did the player produce per opportunity he was given?"
--       EPA_per_recorded_opportunity = offensive_EPA_points_raw
--                                    / recorded_offensive_opportunities
--    Pure efficiency. A volume-blind number: a 13-shot player and a 121-shot
--    player are on the same scale and the 13-shot player's version is almost
--    all noise, which is why the null standard error travels with it.
--
-- 2. "How much value did he produce compared with what a player at his usage
--     level typically produces?"
--       EPA_vs_usage_expectation = offensive_EPA_points_raw
--                                - expected_EPA_given_usage
--    where expected_EPA_given_usage is fitted from the league by
--    cross-validated model selection over {constant, linear, quadratic} in
--    offensive_play_share (scripts/pll_adjusted_value_models.py). No functional
--    form was assumed; see `usage_model_form` for what won.
--
-- 3. "How unusual is that, given how many chances he actually had?"
--       EPA_vs_usage_expectation_z = EPA_vs_usage_expectation
--                                  / offensive_EPA_null_sd
--    This is the column that does the real work of usage adjustment in this
--    project, and the reason is empirical: in 2026 the MEAN of offensive
--    EPA_points barely moves with usage (r = 0.03 with play share among
--    offensive field players, cross-validated R^2 essentially nil) while its
--    VARIANCE moves enormously -- the sd of offensive EPA rises from 1.17 in
--    the lowest usage quintile to 5.58 in the highest. Subtracting a flat mean
--    therefore adjusts almost nothing; dividing by the sampling spread at the
--    player's own volume adjusts exactly the thing that changes.
--
-- ===========================================================================
-- WHAT IS DELIBERATELY NOT HERE
-- ===========================================================================
--
-- There is no `EPA x play_share` column. Multiplying value by usage would pay
-- a player twice for the same shots -- once in the value he generated on them
-- and once for having taken them -- and would make usage a reward in itself,
-- which the Phase 7 brief forbids and which no published Lacrosse Reference
-- methodology supports.
--
-- `uaEPA_per_event_log_play_share` IS published, because Lacrosse Reference's
-- one documented usage adjustment is literally "divide total EGA by play
-- shares" and reproducing it faithfully is part of this phase. It is named for
-- what it is. It should not be read as a cross-position ranking: its
-- denominator is 38 per game for a faceoff specialist and 2.5 per game for a
-- close defender (see the audit in sql/player_play_shares.sql).

CREATE OR REPLACE TABLE player_usage_adjusted_value AS
SELECT
    c.player_id,
    c.player_name,
    c.team_id,
    c.canonical_position,
    c.position_group,
    c.value_role,
    c.games_played,

    -- ---- inputs ----
    c.recorded_offensive_opportunities                   AS recorded_opportunities,
    c.team_recorded_offensive_opportunities,
    c.offensive_play_share                               AS play_share,
    c.offensive_play_share_season,
    c.event_log_play_shares,
    c.event_log_play_share,
    c.offensive_EPA_points_raw,
    c.EPA_points_raw,

    -- ---- 1. efficiency ----
    c.EPA_per_recorded_opportunity                       AS EPA_per_opportunity,
    c.offensive_EPA_null_sd
      / NULLIF(CAST(c.recorded_offensive_opportunities AS DOUBLE), 0)
                                                         AS EPA_per_opportunity_null_se,

    -- ---- 2. value relative to the usage expectation ----
    c.expected_EPA_given_usage,
    c.EPA_vs_usage_expectation,
    c.offensive_EPA_null_sd                              AS EPA_vs_usage_expectation_se,

    -- ---- 3. how unusual, given volume ----
    c.EPA_vs_usage_expectation
      / NULLIF(c.offensive_EPA_null_sd, 0)               AS EPA_vs_usage_expectation_z,
    c.offensive_EPA_points_raw
      / NULLIF(c.offensive_EPA_null_sd, 0)               AS offensive_EPA_null_z,

    -- A 95% interval around the residual, from the same null spread. Published
    -- as an INTERVAL rather than as a p-value on purpose: a p-value invites
    -- reading 228 simultaneous tests as 228 discoveries, and the question here
    -- is "how big could this be by chance", which an interval answers directly.
    CASE WHEN c.recorded_offensive_opportunities > 0
         THEN c.EPA_vs_usage_expectation - 1.96 * c.offensive_EPA_null_sd END
                                                         AS EPA_vs_usage_expectation_ci_lo,
    CASE WHEN c.recorded_offensive_opportunities > 0
         THEN c.EPA_vs_usage_expectation + 1.96 * c.offensive_EPA_null_sd END
                                                         AS EPA_vs_usage_expectation_ci_hi,

    -- ---- the Lacrosse Reference reproduction, clearly labelled ----
    c.uaEPA_per_event_log_play_share,

    -- ---- provenance, on every row ----
    c.usage_model_population,
    c.usage_model_form,
    'offensive_play_share = (shots + turnovers) / same summed over the player''s team '
      || 'in the games he played'                        AS usage_definition,
    'EPA_vs_usage_expectation = offensive_EPA_points_raw - E[offensive EPA | play share], '
      || 'model selected by 5-fold cross-validated MSE from {constant, linear, quadratic}'
                                                         AS method,
    'null sd = sqrt of the closed-form sampling variance of the component at this '
      || 'player''s own opportunity counts, under league-average conversion'
                                                         AS uncertainty
FROM player_adjusted_core c
ORDER BY c.player_id;
