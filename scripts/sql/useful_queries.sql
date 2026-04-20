-- useful analytical queries for montgomery county voter access analysis
-- provides quick access to common summary statistics and insights

-- overall summary statistics for the project
select 
    'Total Block Groups' as metric, count(*)::text as value from population_centers
union all
select 'Total Population', sum(population)::text from population_centers
union all
select 'Polling Places', count(*)::text from polling_places
union all
select 'Matched Precincts (2020-2024)', count(*)::text from turnout_comparison
union all
select 'Avg Walkability Score', round(avg(walkability_score)::numeric, 1)::text from accessibility_scores
union all
select 'Avg Walking Distance (miles)', round(avg(min_google_walking_dist_miles)::numeric, 2)::text from accessibility_scores;

-- top ten most walkable polling places based on average walking distance
select name, centers_served, avg_walking_miles, total_population_served
from polling_coverage
where centers_served > 0
order by avg_walking_miles asc
limit 10;

-- top ten least walkable polling places requiring longest walking distances
select name, centers_served, avg_walking_miles, total_population_served
from polling_coverage
order by avg_walking_miles desc
limit 10;

-- precincts with largest turnout drop from 2020 to 2024
select precinct_name, votes_2020, votes_2024, vote_change, pct_change, 
       avg_walking_miles, avg_walkability_score
from turnout_accessibility_correlation
order by pct_change asc
limit 10;

-- precincts that showed increased turnout between elections
select precinct_name, votes_2020, votes_2024, vote_change, pct_change,
       avg_walking_miles, avg_walkability_score
from turnout_accessibility_correlation
where pct_change > 0
order by pct_change desc;

-- correlation between vote change and accessibility metrics
select 
    corr(vote_change, avg_walking_miles) as correlation_distance,
    corr(vote_change, avg_walkability_score) as correlation_score,
    count(*) as sample_size
from turnout_accessibility_correlation
where avg_walking_miles > 0;

-- walkability demographics summary by category
select * from walkability_demographics;

-- priority areas combining high vulnerability and poor walkability
select geoid, population, pct_black, pct_poverty, 
       min_google_walking_dist_miles, walkability_score
from priority_areas;

-- export ready query for arcgis and looker integration
-- provides complete dataset with all key metrics and spatial geometry
select 
    pc.geoid,
    pc.population,
    pc.latitude,
    pc.longitude,
    d.pct_black,
    d.pct_poverty,
    d.pct_no_vehicle,
    v.vulnerability_category,
    a.min_google_walking_dist_miles,
    a.walkability_score,
    a.walkability_category,
    ppm.polling_name as nearest_polling_place,
    st_astext(a.geom) as wkt_geometry
from population_centers pc
join demographics_bg d on pc.geoid = d.geoid
join vulnerability_index v on pc.geoid = v.geoid
join accessibility_scores a on pc.geoid = a.geoid
left join precinct_polling_map ppm on a.nearest_poll_id = ppm.polling_place_id;