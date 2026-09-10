-- Phase 6: faceoff value.
--
--   faceoff_value = (faceoff_wins - expected_wins) * points_per_marginal_win
--   expected_wins = faceoffs * league faceoff win probability
--
-- The counterfactual is explicit, which is what stops this from being "full
-- possession value for every win". A player who wins draws at the league rate
-- has created nothing relative to an average faceoff man; only wins ABOVE the
-- expected number are credited. The league win probability is the empirical
-- 0.49656, not an assumed 0.5: each draw credits a faceoff to both
-- participants and a win to one, so the ratio would be exactly 0.5 except that
-- 18 of the season's draws have no recorded winner (violations and redraws --
-- see player_value_baselines.sql). Using the empirical rate is what makes the
-- league sum of faceoff_value exactly zero.
--
-- points_per_marginal_win is TWICE the empirical net-points value of a faceoff
-- event. Winning a draw is worth +v to your team; losing the same draw hands
-- +v to the opponent; so converting a loss into a win is worth 2v. v is
-- estimated by the forward-window method (net PLL points in the 60 seconds
-- after the draw, net of the neutral reference) -- see
-- scripts/pll_player_value_models.py.
--
-- NULL, not zero, for a player who never took a faceoff: he has no faceoff
-- opportunities, so his faceoff value is undefined rather than measured-zero.
--
-- Because expected wins are computed against a rate that the league's own wins
-- define, the league sum of faceoff_value is exactly zero. Validation check 15
-- asserts this.

CREATE OR REPLACE TABLE player_faceoff_value AS
SELECT
    o.player_id,
    o.player_name,
    o.primary_team_id,
    o.position_code,
    o.games_played,
    o.faceoffs,
    o.faceoff_wins,
    o.faceoff_losses,
    o.faceoff_win_pct,
    CASE WHEN o.faceoffs > 0 THEN o.faceoffs * c.faceoff_win_probability END
        AS expected_faceoff_wins,
    CASE WHEN o.faceoffs > 0 THEN o.faceoff_wins - o.faceoffs * c.faceoff_win_probability END
        AS faceoff_wins_above_expected,
    CASE WHEN o.faceoffs > 0
         THEN (o.faceoff_wins - o.faceoffs * c.faceoff_win_probability)
              * c.points_per_marginal_faceoff_win END
        AS faceoff_value,
    CASE WHEN o.faceoffs > 0
         THEN ((o.faceoff_wins - o.faceoffs * c.faceoff_win_probability)
               * c.points_per_marginal_faceoff_win) / o.faceoffs END
        AS faceoff_value_per_faceoff
FROM player_opportunities o
CROSS JOIN value_coefficients c
ORDER BY o.player_id;
