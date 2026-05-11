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

create or replace view distance_method_comparison as
select 
    a.geoid,
    pc.population,
    a.min_dist_to_poll_miles as euclidean_miles,
    a.min_manhattan_dist_miles as manhattan_miles,
    a.min_network_dist_miles as osrm_driving_miles,
    a.min_walking_dist_miles as osrm_walking_miles,
    a.min_google_walking_dist_miles as google_walking_miles,
    a.driving_to_euclidean_ratio,
    a.google_walking_to_euclidean_ratio,
    a.osrm_walking_to_driving_ratio,
    a.google_to_osrm_walking_ratio
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
where a.min_google_walking_dist_miles is not null
order by a.min_google_walking_dist_miles desc;

create or replace view isochrone_vulnerability_coverage as
select 
    i.polling_place_name,
    i.time_minutes,
    i.area_sq_miles,
    i.population_served,
    p.latitude as poll_lat,
    p.longitude as poll_lon,
    v.vulnerability_category,
    count(distinct pc.geoid) as nearby_block_groups,
    round(avg(d.pct_black)::numeric, 1) as avg_pct_black,
    round(avg(d.pct_poverty)::numeric, 1) as avg_pct_poverty
from isochrone_summary i
join polling_places p on i.polling_place_name = p.precinct
left join population_centers pc on st_dwithin(
    pc.geom, 
    st_setsrid(st_makepoint(p.longitude, p.latitude), 4326), 
    0.02
)
left join demographics_bg d on pc.geoid = d.geoid
left join vulnerability_index v on pc.geoid = v.geoid
group by i.polling_place_name, i.time_minutes, i.area_sq_miles, 
         i.population_served, p.latitude, p.longitude, v.vulnerability_category
order by i.time_minutes, i.area_sq_miles desc;

create or replace view sidewalk_equity_analysis as
select 
    v.vulnerability_category,
    count(*) as block_groups,
    sum(case when a.osm_has_sidewalk then 1 else 0 end) as blocks_with_sidewalks,
    round(avg(a.osm_sidewalk_pct)::numeric, 1) as avg_sidewalk_coverage_pct,
    round(avg(a.osm_sidewalk_count)::numeric, 0) as avg_sidewalk_segments,
    round(avg(a.walkability_score)::numeric, 1) as avg_walkability_score,
    round(avg(a.min_google_walking_dist_miles)::numeric, 2) as avg_walking_distance
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
join vulnerability_index v on a.geoid = v.geoid
group by v.vulnerability_category
order by v.vulnerability_category;

create or replace view routing_outliers as
select 
    a.geoid,
    pc.population,
    a.min_dist_to_poll_miles as euclidean_miles,
    a.min_google_walking_dist_miles as google_walking_miles,
    a.google_walking_to_euclidean_ratio,
    case 
        when a.google_walking_to_euclidean_ratio > 2.0 then 'Severe detour'
        when a.google_walking_to_euclidean_ratio > 1.5 then 'Moderate detour'
        when a.google_walking_to_euclidean_ratio < 0.8 then 'Direct route'
        else 'Normal'
    end as routing_quality,
    d.pct_black,
    d.pct_poverty,
    a.osm_has_sidewalk,
    a.osm_sidewalk_pct
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
join demographics_bg d on a.geoid = d.geoid
where a.min_google_walking_dist_miles is not null
  and a.google_walking_to_euclidean_ratio > 1.5
order by a.google_walking_to_euclidean_ratio desc;

create or replace view distance_tier_demographics as
select 
    case 
        when a.min_google_walking_dist_miles < 0.5 then 'Under 0.5 miles'
        when a.min_google_walking_dist_miles < 1.0 then '0.5-1.0 miles'
        when a.min_google_walking_dist_miles < 2.0 then '1.0-2.0 miles'
        when a.min_google_walking_dist_miles < 5.0 then '2.0-5.0 miles'
        else 'Over 5 miles'
    end as distance_tier,
    count(*) as block_groups,
    sum(pc.population) as total_population,
    round(avg(d.pct_black)::numeric, 1) as avg_pct_black,
    round(avg(d.pct_poverty)::numeric, 1) as avg_pct_poverty,
    round(avg(d.pct_no_vehicle)::numeric, 1) as avg_pct_no_vehicle,
    count(case when v.vulnerability_category = 'High' then 1 end) as high_vulnerability_count
from accessibility_scores a
join population_centers pc on a.geoid = pc.geoid
join demographics_bg d on a.geoid = d.geoid
join vulnerability_index v on a.geoid = v.geoid
where a.min_google_walking_dist_miles is not null
group by distance_tier
order by min(a.min_google_walking_dist_miles);

-- summary statistics for dashboard landing page
create or replace view dashboard_summary as
select 
    (select count(*) from population_centers) as total_block_groups,
    (select sum(population) from population_centers) as total_population,
    (select count(*) from polling_places) as total_polling_places,
    (select count(*) from turnout_comparison) as matched_precincts,
    (select round(avg(min_google_walking_dist_miles)::numeric, 2) 
     from accessibility_scores) as avg_walking_miles,
    (select round(avg(walkability_score)::numeric, 1) 
     from accessibility_scores) as avg_walkability_score;

-- time-series turnout data for line charts
create or replace view dashboard_turnout_timeline as
select 
    precinct_name,
    votes_2020,
    votes_2024,
    vote_change,
    pct_change,
    avg_walking_miles,
    avg_walkability_score
from turnout_accessibility_correlation;
