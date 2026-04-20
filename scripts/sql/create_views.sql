-- analytical views for montgomery county voter access analysis
-- provides pre-joined datasets for common query patterns

-- priority areas combining high vulnerability and poor walkability
-- identifies block groups with greatest need for intervention
create or replace view priority_areas as
select 
    a.geoid,
    pc.population,
    pc.latitude,
    pc.longitude,
    v.vulnerability_category,
    v.vulnerability_score,
    d.pct_black,
    d.pct_poverty,
    d.pct_no_vehicle,
    a.min_google_walking_dist_miles,
    a.min_walking_dist_miles as osrm_walking_miles,
    a.walkability_category,
    a.walkability_score,
    a.osm_has_sidewalk,
    a.geom
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
join demographics_bg d on a.geoid = d.geoid
join vulnerability_index v on a.geoid = v.geoid
where v.vulnerability_category in ('High')
  and a.walkability_category in ('Poor', 'Very Poor')
order by a.min_google_walking_dist_miles desc;

-- polling coverage statistics aggregated by polling place
-- shows how many residents each polling location serves
create or replace view polling_coverage as
select 
    pp.ogc_fid as id,
    pp.precinct as name,
    pp.address,
    pp.city,
    count(distinct a.geoid) as centers_served,
    round(avg(a.min_google_walking_dist_miles)::numeric, 2) as avg_walking_miles,
    round(avg(a.min_walking_dist_miles)::numeric, 2) as avg_osrm_walking_miles,
    sum(pc.population) as total_population_served,
    pp.wkb_geometry as geom
from polling_places pp
left join accessibility_scores a on pp.ogc_fid = a.nearest_poll_id
left join population_centers pc on a.geoid = pc.geoid
group by pp.ogc_fid, pp.precinct, pp.address, pp.city, pp.wkb_geometry
order by avg_walking_miles;

-- turnout comparison between 2020 and 2024 elections
-- shows vote totals and change for each matched precinct
drop view if exists turnout_comparison;
create view turnout_comparison as
select 
    p24.name as precinct_2024_name,
    m.name_2020 as precinct_2020_name,
    coalesce(e20.dem_pres_votes, 0) + coalesce(e20.rep_pres_votes, 0) + 
    coalesce(e20.lib_pres_votes, 0) + coalesce(e20.writein_pres_votes, 0) as votes_2020,
    coalesce(e24.dem_pres_votes, 0) + coalesce(e24.rep_pres_votes, 0) + 
    coalesce(e24.ind_pres_kennedy_votes, 0) + coalesce(e24.ind_pres_oliver_votes, 0) +
    coalesce(e24.ind_pres_stein_votes, 0) + coalesce(e24.writein_pres_votes, 0) as votes_2024,
    (coalesce(e24.dem_pres_votes, 0) + coalesce(e24.rep_pres_votes, 0) + 
     coalesce(e24.ind_pres_kennedy_votes, 0) + coalesce(e24.ind_pres_oliver_votes, 0) +
     coalesce(e24.ind_pres_stein_votes, 0) + coalesce(e24.writein_pres_votes, 0)) -
    (coalesce(e20.dem_pres_votes, 0) + coalesce(e20.rep_pres_votes, 0) + 
     coalesce(e20.lib_pres_votes, 0) + coalesce(e20.writein_pres_votes, 0)) as vote_change
from precincts_2024 p24
join precinct_name_mapping m on p24.name = m.name_2024
join precincts_2020 p20 on m.name_2020 = p20.name
join election_results_2020 e20 on p20.geoid = e20.precinct_geoid
join election_results_2024 e24 on p24.geoid = e24.precinct_geoid;

-- full analysis combining all demographic and accessibility metrics
-- single comprehensive view for most analytical queries
create or replace view full_analysis as
select 
    pc.geoid,
    pc.population,
    pc.latitude,
    pc.longitude,
    d.total_population as bg_population,
    d.pct_black,
    d.pct_poverty,
    d.pct_no_vehicle,
    d.median_household_income,
    v.vulnerability_score,
    v.vulnerability_category,
    a.min_dist_to_poll_miles as euclidean_dist_miles,
    a.min_manhattan_dist_miles,
    a.min_network_dist_miles as osrm_driving_miles,
    a.min_walking_dist_miles as osrm_walking_miles,
    a.min_google_walking_dist_miles,
    a.walkability_score,
    a.walkability_category,
    a.osm_has_sidewalk,
    a.osm_sidewalk_pct,
    a.driving_to_euclidean_ratio,
    a.osrm_walking_to_euclidean_ratio as walking_to_euclidean_ratio,
    a.osrm_walking_to_driving_ratio as walking_to_driving_ratio,
    ppm.polling_name as nearest_polling_place,
    a.geom
from population_centers pc
join demographics_bg d on pc.geoid = d.geoid
join vulnerability_index v on pc.geoid = v.geoid
join accessibility_scores a on pc.geoid = a.geoid
left join precinct_polling_map ppm on a.nearest_poll_id = ppm.polling_place_id;

-- walkability demographics summary
-- aggregates demographic characteristics by walkability category
create or replace view walkability_demographics as
select 
    a.walkability_category,
    count(*) as block_groups,
    sum(pc.population) as total_population,
    round(avg(d.pct_black)::numeric, 1) as avg_pct_black,
    round(avg(d.pct_poverty)::numeric, 1) as avg_pct_poverty,
    round(avg(d.pct_no_vehicle)::numeric, 1) as avg_pct_no_vehicle,
    round(avg(a.min_google_walking_dist_miles)::numeric, 2) as avg_walking_miles
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
join demographics_bg d on a.geoid = d.geoid
group by a.walkability_category
order by avg_walking_miles;

-- turnout versus accessibility correlation
-- examines relationship between voting participation and walkability
create or replace view turnout_accessibility_correlation as
select 
    t.precinct_2020_name as precinct_name,
    t.votes_2020,
    t.votes_2024,
    t.vote_change,
    round((t.vote_change::numeric / nullif(t.votes_2020, 0) * 100), 1) as pct_change,
    coalesce(round(avg(a.min_google_walking_dist_miles)::numeric, 2), 0) as avg_walking_miles,
    coalesce(round(avg(a.walkability_score)::numeric, 1), 0) as avg_walkability_score,
    count(a.geoid) as block_groups_served
from turnout_comparison t
left join precinct_polling_map ppm on t.precinct_2020_name = ppm.precinct_2020_name
left join accessibility_scores a on ppm.polling_place_id = a.nearest_poll_id
where t.votes_2024 > 0
group by t.precinct_2020_name, t.votes_2020, t.votes_2024, t.vote_change
order by pct_change asc;

-- accessibility analysis complete with tract-level demographics
-- joins accessibility scores with tract-level census data for complete poverty metrics
drop view if exists accessibility_analysis_complete;
create or replace view accessibility_analysis_complete as
select 
    a.geoid as bg_geoid,
    a.min_google_walking_dist_miles as walking_dist_miles,
    a.walkability_score,
    a.walkability_category,
    a.min_dist_to_poll_miles as euclidean_dist_miles,
    a.min_network_dist_miles as osrm_driving_miles,
    a.min_walking_dist_miles as osrm_walking_miles,
    substring(a.geoid, 1, 11) as tract_geoid,
    d.total_pop,
    d.pct_black,
    d.pct_poverty,
    d.pct_no_vehicle,
    d.median_income,
    v.vulnerability_score,
    v.vulnerability_category
from accessibility_scores a
left join demographics_tract_clean d on substring(a.geoid, 1, 11) = d.geoid
left join vulnerability_index_tract v on substring(a.geoid, 1, 11) = v.geoid;