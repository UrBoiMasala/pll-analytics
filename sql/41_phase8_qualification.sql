-- Phase 8: leaderboard qualification rules.
--
-- The rules are DATA, not prose, so a leaderboard row can carry its own reason
-- and a validation check can assert that every rule used exists and that no
-- rule's implied trial count is a round number chosen for convenience.
--
-- Every evidence gate is empirical-Bayes reliability >= 0.5: the point at which
-- the posterior places more weight on the player's own record than on the
-- league prior. That is a property of the estimator, not a preference. The
-- trial count it implies is DIFFERENT FOR EVERY RATE and is set by that rate's
-- own prior strength, which the data estimated -- so the reason strings below
-- are built by joining to Phase 7's published identification table rather than
-- being typed in.
--
-- {scratch_dir} is substituted by scripts/pll_build_phase8_stats.py and holds
-- the one prior strength Phase 8 estimates itself (turnovers per touch), using
-- Phase 6's own beta_prior_by_moments estimator.

CREATE OR REPLACE VIEW p8_rate_identification AS
SELECT * FROM read_csv_auto('{data_dir}/player_rate_identification.csv');

CREATE OR REPLACE VIEW p8_derived_thresholds AS
SELECT * FROM read_csv_auto('{scratch_dir}/phase8_thresholds.csv');


CREATE OR REPLACE TABLE p8_qualification_rules AS

WITH ident AS (
    SELECT rate_name, trials_for_reliability_0_5, n_players_reliability_ge_0_5,
           n_players_with_trials
    FROM p8_rate_identification
),
t AS (SELECT * FROM p8_derived_thresholds)

SELECT * FROM (
    VALUES
    ('NONE_COUNTING', 'none',
     'A counting statistic. A count is not an estimate of a rate, so no evidence gate applies: '
     || 'the number IS the season. Sample size still travels on the row as the denominator.'),

    ('DESCRIPTIVE_VALUE_TOTAL', 'played at least one eligible game (or had at least one opportunity of the relevant class)',
     'A value TOTAL, not a rate. Totals scale with opportunity, so gating them on rate reliability '
     || 'would remove exactly the players whose volume makes the total large. The denominator on the '
     || 'row is the opportunity base, and cross-position comparison of these totals is invalid '
     || '(Phase 7: opportunity bases differ by 6.6x in observed spread).'),

    ('ANY_TRIAL_SHRUNK', 'at least one trial of the rate',
     'A shrunk estimate exists for anyone with at least one trial, because the prior supplies the '
     || 'rest. No reliability gate is applied to a shrunk rate: shrinkage is the small-sample '
     || 'handling. Read it as an ABILITY estimate, never as what happened in 2026 -- the raw '
     || 'counterpart on the same row is what happened.'),

    ('USAGE_MODEL_POPULATION', 'field player with at least one recorded offensive opportunity',
     'The Phase 7 usage model was fitted on field players only; expected_EPA_given_usage is NULL '
     || 'for goalies and faceoff specialists because no offensive-usage expectation is defined for '
     || 'them. NULL, not zero, because zero would be a claim.'),

    ('NOT_QUALIFIABLE_TWO_POINT', 'no player can qualify',
     'DELIBERATELY EMPTY. The 2026 between-player two-point variance (0.0234) is SMALLER than '
     || 'binomial noise alone predicts (0.0276), so the estimated prior strength is capped at 1e6, '
     || 'every shrunk rate equals the league mean and every reliability is below 0.001. No two-point '
     || 'ability leaderboard is published for any sample size. The absence of a QUALIFIED scope for '
     || 'this metric is the finding, not an omission.')
) AS s(qualification_rule, qualification_rule_short, qualification_reason)

UNION ALL SELECT 'SHOOTING_RELIABILITY_HALF',
    'shooting_reliability >= 0.5',
    'Empirical-Bayes reliability n/(n+kappa) >= 0.5 on shooting percentage, i.e. at least '
    || ROUND(i.trials_for_reliability_0_5, 1) || ' shot attempts (kappa estimated from the 2026 league by '
    || 'method of moments; NOT a round number chosen for convenience). '
    || i.n_players_reliability_ge_0_5 || ' of ' || i.n_players_with_trials || ' shooters clear it.'
FROM ident i WHERE i.rate_name = 'shooting_pct'

UNION ALL SELECT 'ONE_POINT_RELIABILITY_HALF',
    'one_point_reliability >= 0.5',
    'Empirical-Bayes reliability >= 0.5 on one-point conversion, i.e. at least '
    || ROUND(i.trials_for_reliability_0_5, 1) || ' one-point attempts. '
    || i.n_players_reliability_ge_0_5 || ' of ' || i.n_players_with_trials || ' clear it.'
FROM ident i WHERE i.rate_name = 'one_point_pct'

UNION ALL SELECT 'FACEOFF_RELIABILITY_HALF',
    'faceoff_reliability >= 0.5',
    'Empirical-Bayes reliability >= 0.5 on faceoff win percentage, i.e. at least '
    || ROUND(i.trials_for_reliability_0_5, 1) || ' draws. Faceoff is the most strongly identified rate '
    || 'in the framework (implied true between-player sd 0.122); '
    || i.n_players_reliability_ge_0_5 || ' of ' || i.n_players_with_trials || ' faceoff takers clear it.'
FROM ident i WHERE i.rate_name = 'faceoff_win_pct'

UNION ALL SELECT 'SAVE_RELIABILITY_HALF',
    'save_reliability >= 0.5',
    'Empirical-Bayes reliability >= 0.5 on save percentage, i.e. at least '
    || ROUND(i.trials_for_reliability_0_5, 1) || ' save-percentage trials -- saves plus goals '
    || 'allowed, which is the base the official rate is defined on and the base Phase 7 estimated '
    || 'the prior from. It is NOT shots_on_goal_faced: the event log records 2,567 shots on goal '
    || 'against 2,412 official trials, because some shots on goal resolve as neither a save nor a '
    || 'goal in the box score. Only '
    || i.n_players_reliability_ge_0_5 || ' of ' || i.n_players_with_trials || ' goalies clear it, because '
    || 'the busiest keeper in the league faced fewer shots than the prior strength. A one-row '
    || 'QUALIFIED leaderboard is the correct output of this rule, not a defect: 2026 alone cannot '
    || 'separate goalies on save percentage. Use the ALL scope, with the trial count, to describe '
    || 'the season.'
FROM ident i WHERE i.rate_name = 'save_pct'

UNION ALL SELECT 'OFFENSIVE_RATE_RANKING_ELIGIBLE',
    'Phase 7 offensive_rate_ranking_eligible',
    'Phase 7 flag: shooting reliability >= 0.5. Phase 7 gates offensive EFFICIENCY metrics on the '
    || 'shooting rate specifically, and not on a player role rate, so that a faceoff specialist who '
    || 'is superbly identified on draws cannot be licensed onto a per-shot efficiency leaderboard by '
    || 'that identification. 13 of 228 players clear it.'

UNION ALL SELECT 'TURNOVER_RATE_RELIABILITY_HALF',
    'touches >= ' || ROUND(t.turnover_rate_kappa, 1),
    'Empirical-Bayes reliability >= 0.5 on turnovers per touch, i.e. at least '
    || ROUND(t.turnover_rate_kappa, 1) || ' touches. The prior strength is estimated in Phase 8 using '
    || 'Phase 6''s own beta_prior_by_moments estimator (imported, not reimplemented) so it is '
    || 'consistent with every other gate here. SEPARATE CAVEAT that no threshold fixes: roughly 19% '
    || 'of league turnovers are attributed to no player at all, because the feed''s turnover '
    || 'descriptions name only a team. Every player-level turnover rate is therefore understated by '
    || 'an unknown, non-uniform amount.'
FROM t

ORDER BY 1;
