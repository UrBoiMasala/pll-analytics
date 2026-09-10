"""Generate the proposed final catalog and inventory; no new analytics model.

The catalog is a specification. Only the retained foundation is rebuilt during
refocus. Existing research outputs stay in place and are classified explicitly.
"""
from pathlib import Path
import csv
import json
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / 'data/processed/history'
DOC = ROOT / 'docs'
# category, name, formula, unit, classification, source, interpretation
METRICS = [
('TEAM','possessions_per_game','P / GP','possessions/game','DERIVED_ADVANCED','possessions + games','Reconstructed team pace; regulation and overtime combined.'),
('TEAM','offensive_efficiency','100 * Q / P','PLL points/100 possessions','DERIVED_ADVANCED','possessions','Points produced on reconstructed offensive possessions.'),
('TEAM','defensive_efficiency','100 * Q_allowed / P_def','PLL points/100 possessions','DERIVED_ADVANCED','possessions','Points allowed on reconstructed defensive possessions.'),
('TEAM','net_efficiency','offensive_efficiency - defensive_efficiency','PLL points/100 possessions','DERIVED_ADVANCED','possessions','Difference between team scoring and conceding rates.'),
('TEAM','shots_per_possession','A / P','attempts/possession','DERIVED_ADVANCED','eligible events + possessions','Shot generation per reconstructed possession.'),
('TEAM','turnovers_per_possession','U_team / P','turnovers/possession','DERIVED_ADVANCED','team_game_stats + possessions','Official team turnovers per reconstructed possession, including team-only turnovers.'),
('TEAM','shot_clock_expirations_per_possession','C / P','expirations/possession','DERIVED_ADVANCED','eligible events + possessions','Frequency of logged shot-clock expiration events.'),
('TEAM','mean_possession_span','mean(duration_seconds where M)','seconds','DERIVED_ADVANCED','possessions','Average observed span, restricted to measurable boundaries; not full possession duration.'),
('TEAM','median_possession_span','median(duration_seconds where M)','seconds','DERIVED_ADVANCED','possessions','Median observed span over the same subset; less sensitive to long spans.'),
('OFFENSE','shooting_pct','(G1 + G2) / (A1 + A2)','proportion','STANDARD','eligible shot events','Conversion of all logged attempts into goals, independent of point value.'),
('OFFENSE','shots_on_goal_pct','SOG / A','proportion','DERIVED_ADVANCED','eligible shot events','Share of logged attempts classified as on goal; retain unresolved on-goal class count.'),
('OFFENSE','scoring_points_per_shot','(G1 + 2*G2) / (A1 + A2)','PLL scoring points/attempt','DERIVED_ADVANCED','eligible shot events','Scoring return on shots. Assists excluded; traditional player points are a separate context field.'),
('OFFENSE','turnovers_per_touch','U / T','turnovers/touch proxy','DERIVED_ADVANCED','player_game_stats','Recorded ball security per feed touch count; not passing value.'),
('OFFENSE','turnovers_below_expected','T * u_s - U','turnover events','DERIVED_ADVANCED','player_game_stats','Recorded turnovers avoided relative to a season league touch baseline; positive means fewer turnovers.'),
('OFFENSE','shooting_value_above_expected','G1 + 2*G2 - A1*p1_s - 2*A2*p2_s','PLL scoring points','ORIGINAL_PLL_METRIC','eligible shot events','Scoring above season-average conversion on the same 1PT/2PT shot mix; no total-offense claim.'),
('PLL_2PT','two_point_attempt_rate','A2 / (A1 + A2)','proportion','DERIVED_ADVANCED','eligible shot events','Shot selection: frequency of choosing the two-point shot.'),
('PLL_2PT','two_point_conversion_pct','G2 / A2','proportion','STANDARD','eligible shot events','Observed two-point conversion; not persistent shooting ability.'),
('PLL_2PT','two_point_shooting_value','2 * (G2 - A2*p2_s)','PLL scoring points','ORIGINAL_PLL_METRIC','eligible shot events','The two-point component of shooting value; never add it again to total shooting value.'),
('PLL_2PT','team_two_point_attempt_share','sum_g A2_player_g / sum_g A2_team_g','proportion','DERIVED_ADVANCED','eligible events + player-game participation','Share of team two-point attempts in the games the player appeared, respecting actual team in each game.'),
('FACEOFF','faceoff_pct','W / F','proportion','STANDARD','player_game_stats','Observed faceoff success with attempts and unassigned outcomes visible.'),
('FACEOFF','draw_share','sum_g F_player_g / sum_g F_team_g','proportion','DERIVED_ADVANCED','player_game_stats + team_game_stats','Draw workload in appearances, following actual game team for transfers.'),
('FACEOFF','faceoff_wins_above_average','W - F*f_s','faceoff wins','DERIVED_ADVANCED','player_game_stats','Additional wins relative to all recorded league faceoff takers in that season; no point conversion.'),
('GOALIE','save_pct','SV / (SV + GA)','proportion','STANDARD','player_game_stats','Observed saves among resolved saves and goals allowed; shots-faced denominator is explicitly resolved shots.'),
('GOALIE','one_point_save_pct','SV1 / (SV1 + GA1)','proportion','DERIVED_ADVANCED','eligible saved/goal events with goalie_id','Observed one-point stopping among resolved attributable events; show attribution coverage.'),
('GOALIE','two_point_save_pct','SV2 / (SV2 + GA2)','proportion','DERIVED_ADVANCED','eligible saved/goal events with goalie_id','Observed two-point stopping among resolved attributable events; show coverage and small denominator.'),
('GOALIE','saves_above_average','SV - (SV + GA)*s_s','saves','DERIVED_ADVANCED','player_game_stats','Saves above season league stopping results at the same resolved workload; not shot-quality adjusted.'),
('DEFENSE','caused_turnovers_per_game','CT / GP','events/game','DERIVED_ADVANCED','player_game_stats','Recorded disruption, without individual defensive exposure adjustment.'),
('DEFENSE','ground_balls_per_game','GB / GP','events/game','DERIVED_ADVANCED','player_game_stats','Recorded recoveries, including faceoff-related recoveries; no impact composite.'),
('DEFENSE','penalties_per_game','PEN / GP','penalties/game','DERIVED_ADVANCED','player_game_stats','Penalty frequency per appearance, not per defensive possession or minute.'),
]
CONTEXT = {'games_played','points','goals','one_point_goals','two_point_goals','shots','shots_on_goal',
           'turnovers','touches','saves','goals_allowed','faceoffs','faceoff_wins','faceoff_losses',
           'ground_balls','caused_turnovers','penalties','assists','official_assists','two_point_attempts',
           'two_point_points','two_point_goals_allowed','measurable_span_possessions','ambiguous_offensive_possession_share','games_with_unresolved_validation_issue','one_point_attempts','points_scored','points_allowed','offensive_possessions','defensive_possessions'}
ALIASES = {'team_possessions_per_game':'possessions_per_game','shot_clock_expiration_rate':'shot_clock_expirations_per_possession',
           'shooting_value':'shooting_value_above_expected','shooting_value_two_point':'two_point_shooting_value',
           'shooting_value_two_point_raw':'two_point_shooting_value','faceoff_team_share':'draw_share',
           'save_pct_official':'save_pct','offensive_efficiency_per_100':'offensive_efficiency',
           'defensive_efficiency_per_100':'defensive_efficiency','net_efficiency_per_100':'net_efficiency','points_per_shot':'scoring_points_per_shot','shooting_value_raw':'shooting_value_above_expected',
           'two_point_shot_share':'two_point_attempt_rate','faceoff_win_pct':'faceoff_pct',
           'mean_measurable_span_seconds':'mean_possession_span','median_measurable_span_seconds':'median_possession_span',
           'points_per_possession':'offensive_efficiency','two_point_pct':'two_point_conversion_pct'}


def write_csv(name, rows):
    pd.DataFrame(rows).to_csv(HIST/name, index=False)


def main():
    cols = ['category','metric_name','formula','unit','classification','source','interpretation']
    final = [dict(zip(cols,r), scope='PROPOSED; final publication layer not built',
                  zero_denominator='NULL; never rank no-opportunity rows',
                  qualification='Show denominator; user-set filters, no inferred talent qualification') for r in METRICS]
    write_csv('final_metric_catalog.csv',final)
    fdict = {r['metric_name']:r for r in final}
    records = {}
    for name in ['metric_catalog_2026.csv','metric_definitions.csv','player_value_metric_definitions.csv','player_adjusted_metric_definitions.csv']:
        path = ROOT/'data/processed/2026'/name
        for r in pd.read_csv(path).fillna('').to_dict('records'):
            metric = r['metric_name']
            formula = r.get('formula') or (str(r.get('numerator','')) + ' / ' + str(r.get('denominator','')))
            records.setdefault(metric, dict(metric_name=metric, category=r.get('category') or r.get('level','legacy'),
                    current_formula=formula, current_source=r.get('source') or r.get('source_table',''),
                    interpretation=r.get('interpretation') or r.get('definition',''),
                    definition_reference='data/processed/2026/'+name))
    # Include named Phase 13 estimates and diagnostics, beyond the Phase 8 catalog.
    for metric, formula in {
        'offensive_value':'shooting_value_raw + turnover_value_raw',
        'faceoff_value':'(wins - attempts*p_league)*legacy_event_window_coefficient',
        'goalie_value':'expected_points_allowed - observed_points_allowed',
        'defensive_value_partial_raw':'(CT - games*position_CT_per_game)*turnover_coefficient',
        'pairwise_probability':'mean(draws_A > draws_B); offense labels misaligned in archived implementation (I1)',
        'rank_interval':'quantiles of simulated ranks; conditional replay only',
        'top10_probability':'mean(simulated rank <= 10); I2/I6 affected',
        'value_interval':'binomial replay quantiles with fixed baselines and workload; I2 affected',
        'shrinkage_sensitivity':'(season_shrunk_shooting_rate - altered_scope_rate)*shots + turnover_value; mixed units (I7)',
        'team_value_accounting':'sum season player values by modal team; transfer attribution wrong (I5)',
    }.items():
        records.setdefault(metric,dict(metric_name=metric,category='legacy_research',current_formula=formula,
                          current_source='scripts/pll_phase13_*.py',interpretation='Archived research output, not a final metric',definition_reference='docs/AUDIT_REMEDIATION.md'))
    phase13_formulas = {
        'value_ci_lo': '2.5th percentile of 1000 conditional binomial replay values',
        'value_ci_hi': '97.5th percentile of 1000 conditional binomial replay values',
        'value_boot_sd': 'population standard deviation of conditional replay values',
        'rank_ci_lo': '2.5th percentile of descending double-argsort ranks',
        'rank_ci_hi': '97.5th percentile of descending double-argsort ranks',
        'top10_inclusion_frequency': 'mean(simulated rank <= 10)',
        'role_rate_reliability': 'role-specific empirical-Bayes n/(n+k) reliability',
        'faceoff_value_total': 'faceoff_value_raw',
        'faceoff_rate_value': 'faceoff_value_total * mean(role faceoffs) / faceoffs',
        'faceoff_volume_value': 'faceoff_value_total - faceoff_rate_value',
        'baseline_faceoff_win_pct': 'wins / faceoffs summed over role subset; wrong baseline for old simulation (I2)',
        'goalie_value_total': 'expected_points_allowed - observed_points_allowed',
        'goalie_rate_value': 'goalie_value_total * mean(role shots_on_goal_faced) / shots_on_goal_faced',
        'goalie_workload_value': 'goalie_value_total - goalie_rate_value',
        'expected_points_allowed': 'SOG1 * season_1PT_points_allowed_per_SOG + SOG2 * season_2PT_points_allowed_per_SOG',
        'observed_points_allowed': 'goals_allowed + two_point_goals_allowed',
    }
    for metric, formula in phase13_formulas.items():
        records.setdefault(metric, dict(metric_name=metric, category='legacy_research', current_formula=formula,
                 current_source='scripts/pll_phase13_player_value_v1.py', interpretation='Archived conditional research statistic',
                 definition_reference='docs/AUDIT_REMEDIATION.md'))
    for metric in CONTEXT:
        records.setdefault(metric,dict(metric_name=metric,category='context',current_formula='Recorded count; sum over eligible games',
                   current_source='canonical events or player/team_game_stats; see final source contract',interpretation='Context count',definition_reference='docs/FINAL_METRIC_CATALOG.md'))
    for metric, r in records.items():
        target=ALIASES.get(metric,metric)
        kept=target in fdict or metric in CONTEXT
        caveat=kept and (metric not in CONTEXT or metric in {'touches','turnovers','shots_on_goal'})
        status='KEEP_WITH_CAVEAT' if caveat else ('KEEP' if kept else 'ARCHIVE')
        if metric in ALIASES: status='SIMPLIFY'
        if any(t in metric.lower() for t in ['epa','composite','award','tewaaraton','war_']): status='REMOVE_FROM_FINAL_PRODUCT'
        r.update(complexity='LOW' if kept else 'VARIES; not retained',data_quality='Source coverage limitations apply',
                 known_bug={'pairwise_probability':'I1','faceoff_value':'I2 uncertainty only','top10_probability':'I2/I6',
                            'shrinkage_sensitivity':'I7','team_value_accounting':'I5'}.get(metric,'See audit disposition; no claim of exhaustive bug absence'),
                 double_counting_risk='Do not sum related components; two-point value is part of shooting value',
                 easy_to_explain='YES' if kept else 'Not required for archived research',useful_to_fan_or_analyst='YES' if kept else 'Research/reference only',
                 original_or_standard=fdict[target]['classification'] if target in fdict else ('QUALITY_METADATA' if metric in {'measurable_span_possessions','ambiguous_offensive_possession_share','games_with_unresolved_validation_issue'} else ('STANDARD' if metric in CONTEXT else 'EXPERIMENTAL')),
                 final_status=status,reason=('Retained as '+target if kept else 'Outside the small final catalog; preserved for reference, excluded from publication'))
    inventory=sorted(records.values(),key=lambda r:r['metric_name'])
    write_csv('final_metric_inventory.csv',inventory)
    lines=['# Final metric inventory','',f'{len(inventory)} named metrics inventoried from all four existing definition catalogs, contextual counts, and Phase 13 outputs. Technical IDs, flags, validator counts and raw schema fields are not statistical metrics. The machine-readable CSV retains formulas, sources, interpretations and every decision field.','',
           'Aliases and redundant units marked SIMPLIFY map to the canonical names in FINAL_METRIC_CATALOG. ARCHIVE does not mean the formula is wrong; it means it is outside the final product. These decisions override old CORE/production labels.','',
           '| Metric | Decision | Reason |','|---|---|---|']
    lines += ['| '+r['metric_name']+' | '+r['final_status']+' | '+r['reason']+' |' for r in inventory]
    (DOC/'FINAL_METRIC_INVENTORY.md').write_text('\n'.join(lines)+'\n')
    lines=['# Proposed final metric catalog','',f'{len(final)} core metrics; box-score context is additional and is not marketed as advanced analytics. Metrics are proposed here, not a claim that the final SQL layer is implemented.','',
           'All ratios are stored as proportions; display percentages multiply by 100. All zero denominators return NULL. Opportunity-based surplus metrics also return NULL at zero exposure and are excluded from corresponding leaderboards. No universal score and no offensive composite are proposed. ORIGINAL_PLL_METRIC means a PLL-specific adaptation in this project, not a claim of first invention.','',
           '## Shared definitions','',
           'Scope: completed regular-season and playoff games in each frozen season; all-star/exhibition games excluded. 2026 is a partial snapshot through the last included completed game, not a full season. League rates use the same season and eligibility scope; they include the focal player. These are retrospective descriptive baselines, never forward prediction. Default historical comparisons must disclose postseason inclusion.','',
           'GP = appearances (players) or eligible games (teams); P/P_def = reconstructed offensive/defensive possessions; Q = possession PLL scoring points; A1/A2 = eligible one-/two-point attempts; G1/G2 = valid goals in those classes; A=A1+A2; SOG includes goal, saved and on_goal_no_save. C = eligible shotclockexpired event count. M = unambiguous, nontruncated possession with distinct start/end event IDs.','',
           'T/U = recorded player touches/turnovers; u_s = sum(U)/sum(T) across all eligible player-game records with positive T in season s. Report excluded zero/missing-T turnover records separately; never silently assign them an exposure. No position-specific baseline. W/F = recorded wins/attempts; f_s = sum(W)/sum(F) over all league takers with F>0. Actual baseline is preferred over 50% because feed attempts and assigned wins can differ; expose the league baseline as context, not a second near-identical leaderboard.','',
           'SV/GA = box-score saves/goals allowed, with each goal counted once regardless of PLL point value. s_s = sum(SV)/sum(SV+GA) over goalies with resolved shots. Event class SV1/GA1 and SV2/GA2 require an attributed goalie and a resolved saved/goal outcome; unresolved on-goal events are excluded and counted explicitly. Class coverage versus box totals must accompany these optional class-rate columns.','',
           'p1_s=sum(G1)/sum(A1); p2_s=sum(G2)/sum(A2), using all eligible league shot events in season s. Publish baseline attempts and goals. Rates are weighted by attempts, never averages of player percentages. CT/GB/PEN = official caused turnovers/ground balls/penalty counts.','',
           'Transferred players: sum numerator and denominator by actual (season, game, team, player). Season totals combine stints; team displays retain stints. Team workload shares use only player appearances and the actual team in each appearance; they are not season availability shares.','',
           'Historical exception: the known 2022 Archers–Cannons scoring gap is flagged, not imputed. Team Q uses reconstructed scoring; official scoreboard totals are separate context. Show reconciliation status and offer exclusion of the affected game for comparisons.','']
    for category in dict.fromkeys(r['category'] for r in final):
        lines += ['## '+category,'','| Metric | Formula | Units | Classification |','|---|---|---|---|']
        for r in final:
            if r['category']==category: lines.append('| '+r['metric_name']+' | `'+r['formula']+'` | '+r['unit']+' | '+r['classification']+' |')
        lines += ['']+[f"- **{r['metric_name']}**: {r['interpretation']} Source: {r['source']}." for r in final if r['category']==category]+['']
    lines += ['## Context and filtering','',
              'Context fields (STANDARD): games played, goals, 1PT/2PT goals, assists, traditional player points, attempts, shots on goal, touches, turnovers, faceoff attempts/wins/losses, saves, goals allowed, caused turnovers, ground balls and penalties. Keep PLL scoring points (=G1+2G2) distinct from traditional player points (=G1+2G2+assists). Two-point scoring points (=2G2) are context.','',
              'No empirical-Bayes QUALIFIED label in the final product. Always show opportunities and let queries choose a stated minimum (for example 20 attempts). Such thresholds are usability filters, not reliability claims. A zero-opportunity player remains in the roster summary but has NULL rates and no corresponding rate rank. No estimated true two-point talent, rank probability, or predictive interval is published.','']
    (DOC/'FINAL_METRIC_CATALOG.md').write_text('\n'.join(lines))
    # Every existing tracked artifact gets a lifecycle decision; nothing is moved.
    import subprocess
    files=sorted(set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()))
    active_names={'games.csv','teams.csv','players.csv','events.csv','possessions.csv','player_game_stats.csv','team_game_stats.csv',
                  'team_game_advanced.csv','team_season_advanced.csv','team_rankings.csv','possession_length_splits.csv','team_metric_sensitivity.csv'}
    lifecycle=[]
    for path in files:
        status='ARCHIVED'
        why='Prior research/reference; old labels do not authorize final publication'
        if path.startswith('data/raw/') or (path.startswith('data/processed/') and Path(path).name in active_names):
            status='ACTIVE';why='Retained data foundation; canonical v2 applies to listed derived artifacts'
        elif path.startswith(('tests/','scripts/','sql/')):
            status='EXPERIMENTAL';why='Legacy regression/research tooling; use refocus entry point for active rebuild'
        if 'shot_model_validation' in path: status='EXPERIMENTAL';why='Corrected retrospective diagnostic only'
        if Path(path).name.startswith(('refocus_', 'final_metric_', 'audit_remediation', 'artifact_lifecycle', 'CANONICAL_MANIFEST_V2', 'player_team_stints')) or path in {
            'README.md','scripts/pll_refocus_foundation.py','scripts/pll_refocus_catalog.py','scripts/pll_validate_refocus.py',
            'scripts/pll_canonical_versions.py','scripts/pll_build_possessions.py','scripts/pll_build_tables.py',
            'scripts/pll_chronology_repair.py','scripts/pll_duplicate_faceoff.py','scripts/pll_pbp_clean.py',
            'scripts/pll_ingest_season.py','scripts/pll_build_team_metrics.py','sql/00_base_views.sql',
            'sql/team_game_advanced.sql','sql/team_season_advanced.sql','sql/team_rankings.sql',
            'sql/possession_length_splits.sql','sql/team_metric_sensitivity.sql'}:
            status='ACTIVE';why='Refocus specification, validation or retained foundation'
        if path.startswith('docs/') and Path(path).name in {'PROJECT_REFOCUS.md','FINAL_METRIC_CATALOG.md','FINAL_METRIC_INVENTORY.md',
            'METRIC_LIMITATIONS.md','AUDIT_REMEDIATION.md','CANONICAL_DATASET_V2.md','DATA_PIPELINE.md','DATA_VALIDATION.md',
            'POSSESSION_METHODOLOGY.md','ADVANCED_METRICS.md','SQL_GUIDE.md','REFOCUS_VALIDATION_RESULTS.md'}:
            status='ACTIVE';why='Current public-facing documentation'
        lifecycle.append(dict(path=path,status=status,reason=why))
    write_csv('artifact_lifecycle.csv',lifecycle)
    print(f'Proposed metrics: {len(final)}; inventoried metrics: {len(inventory)}; classified artifacts: {len(lifecycle)}')

if __name__ == '__main__':
    main()
