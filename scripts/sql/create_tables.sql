-- complete database schema for montgomery county voter access analysis
-- creates all tables with appropriate data types and spatial indexes

-- enable postgis extension for spatial data handling
create extension if not exists postgis;


-- demographics at block group level
-- stores census acs data with calculated percentages

drop table if exists demographics_bg cascade;
create table demographics_bg (
    geoid varchar(12) primary key,
    total_population integer,
    white_alone integer,
    black_alone integer,
    asian_alone integer,
    hispanic_total integer,
    median_household_income integer,
    poverty_total integer,
    poverty_below integer,
    total_households integer,
    households_no_vehicle integer,
    pop_25_plus integer,
    bachelors_plus integer,
    pct_black double precision generated always as (
        case when total_population > 0 
             then black_alone::double precision / total_population * 100 
             else null end
    ) stored,
    pct_poverty double precision generated always as (
        case when poverty_total > 0 
             then poverty_below::double precision / poverty_total * 100 
             else null end
    ) stored,
    pct_no_vehicle double precision generated always as (
        case when total_households > 0 
             then households_no_vehicle::double precision / total_households * 100 
             else null end
    ) stored
);


-- population centers with weighted coordinates
-- stores census 2020 population-weighted centroids for each block group

drop table if exists population_centers cascade;
create table population_centers (
    geoid varchar(12) primary key references demographics_bg(geoid),
    population integer,
    latitude double precision,
    longitude double precision
);
select AddGeometryColumn('population_centers', 'geom', 4326, 'POINT', 2);
create index idx_pop_centers_geom on population_centers using gist (geom);


-- polling places
-- contains physical locations of all montgomery county polling places

drop table if exists polling_places cascade;
create table polling_places (
    ogc_fid serial primary key,
    fid_alabam integer,
    matchtype varchar(50),
    nummatch varchar(50),
    precinctnu varchar(10),
    precinct varchar(200),
    address varchar(200),
    city varchar(50),
    zip integer,
    county varchar(50),
    state varchar(2),
    fld_zone varchar(10),
    zone_subty varchar(50),
    polling_place_id varchar(20),
    longitude double precision,
    latitude double precision
);
select AddGeometryColumn('polling_places', 'wkb_geometry', 4326, 'POINT', 2);
create index idx_polling_places_geom on polling_places using gist (wkb_geometry);


-- accessibility scores
-- comprehensive distance and walkability metrics for each population center

drop table if exists accessibility_scores cascade;
create table accessibility_scores (
    id serial primary key,
    statefp varchar(2),
    countyfp varchar(3),
    tractce varchar(6),
    blkgrpce varchar(1),
    population integer,
    latitude double precision,
    longitude double precision,
    geoid varchar(12),
    min_dist_to_poll_miles double precision,
    nearest_polling_idx integer,
    min_manhattan_dist_miles double precision,
    min_dist_to_civic_center_miles double precision,
    dist_to_city_hall_miles double precision,
    min_dist_to_poll_miles_norm double precision,
    min_manhattan_dist_miles_norm double precision,
    min_dist_to_civic_center_miles_norm double precision,
    accessibility_score_val double precision,
    accessibility_category varchar(20),
    min_network_dist_miles double precision,
    nearest_poll_network_idx integer,
    driving_to_euclidean_ratio double precision,
    driving_euclidean_diff_miles double precision,
    min_walking_dist_miles double precision,
    nearest_poll_walking_idx integer,
    osrm_walking_to_euclidean_ratio double precision,
    min_google_walking_dist_miles double precision,
    nearest_poll_google_walking_idx integer,
    google_walking_to_euclidean_ratio double precision,
    osrm_walking_to_driving_ratio double precision,
    google_to_osrm_walking_ratio double precision,
    google_walking_to_driving_ratio double precision,
    osm_has_sidewalk boolean,
    osm_sidewalk_count integer,
    osm_total_segments integer,
    osm_sidewalk_pct double precision,
    walkability_score double precision,
    walkability_category varchar(20),
    nearest_poll_id integer references polling_places(ogc_fid),
    created_at timestamp default current_timestamp
);
select AddGeometryColumn('accessibility_scores', 'geom', 4326, 'POINT', 2);
create index idx_accessibility_geoid on accessibility_scores(geoid);
create index idx_accessibility_poll_id on accessibility_scores(nearest_poll_id);


-- precinct boundaries for 2020 election
-- spatial boundaries of voting precincts as they existed in 2020

drop table if exists precincts_2020 cascade;
create table precincts_2020 (
    geoid varchar(20) primary key,
    name varchar(200),
    county_fips varchar(3),
    state_fips varchar(2)
);
select AddGeometryColumn('precincts_2020', 'geom', 4326, 'MULTIPOLYGON', 2);


-- precinct boundaries for 2024 election
-- spatial boundaries of voting precincts after redistricting

drop table if exists precincts_2024 cascade;
create table precincts_2024 (
    geoid varchar(100) primary key,
    name varchar(200),
    county_fips varchar(3),
    state_fips varchar(2)
);
select AddGeometryColumn('precincts_2024', 'geom', 4326, 'MULTIPOLYGON', 2);


-- election results for 2020 general election
-- vote counts aggregated by precinct

drop table if exists election_results_2020 cascade;
create table election_results_2020 (
    id serial primary key,
    precinct_geoid varchar(20) references precincts_2020(geoid),
    dem_pres_votes integer default 0,
    rep_pres_votes integer default 0,
    lib_pres_votes integer default 0,
    writein_pres_votes integer default 0,
    dem_senate_votes integer default 0,
    rep_senate_votes integer default 0
);


-- election results for 2024 general election
-- vote counts aggregated by precinct

drop table if exists election_results_2024 cascade;
create table election_results_2024 (
    id serial primary key,
    precinct_geoid varchar(100) references precincts_2024(geoid),
    dem_pres_votes integer default 0,
    rep_pres_votes integer default 0,
    ind_pres_kennedy_votes integer default 0,
    ind_pres_oliver_votes integer default 0,
    ind_pres_stein_votes integer default 0,
    writein_pres_votes integer default 0
);


-- vulnerability index at block group level
-- composite score identifying communities with multiple accessibility barriers

drop table if exists vulnerability_index cascade;
create table vulnerability_index (
    geoid varchar(12) primary key references demographics_bg(geoid),
    z_pct_black double precision,
    z_pct_poverty double precision,
    z_pct_no_vehicle double precision,
    vulnerability_score double precision,
    vulnerability_category varchar(20)
);


-- isochrone summary statistics
-- aggregated metrics for walkable areas around each polling place

drop table if exists isochrone_summary cascade;
create table isochrone_summary (
    id serial primary key,
    polling_place_name varchar(200),
    time_minutes integer,
    area_sq_miles double precision,
    population_served integer,
    created_at timestamp default current_timestamp
);


-- county-level voter turnout
-- registration and participation statistics for montgomery county

drop table if exists county_turnout cascade;
create table county_turnout (
    id serial primary key,
    county_name varchar(50),
    election_year integer,
    registered_voters integer,
    total_ballots integer,
    absentee_ballots integer,
    provisional_ballots integer
);


-- precinct name crosswalk between 2024 and 2020
-- enables comparative analysis despite redistricting changes

drop table if exists precinct_name_mapping cascade;
create table precinct_name_mapping (
    id serial primary key,
    name_2024 varchar(200),
    name_2020 varchar(200)
);


-- precinct to polling place location mapping
-- connects precinct names to physical voting facility locations

drop table if exists precinct_polling_map cascade;
create table precinct_polling_map (
    precinct_2020_name varchar(200) primary key,
    polling_place_id integer references polling_places(ogc_fid),
    polling_name varchar(200)
);


-- tract-level demographics setup with complete poverty data
-- poverty estimates are available at tract level but suppressed at block group



-- raw tract demographics import table
-- stores data exactly as it appears in the csv import file

drop table if exists demographics_tract cascade;
create table demographics_tract (
    geoid text,
    name text,
    total_pope text,
    total_popm text,
    white_alonee text,
    white_alonem text,
    black_alonee text,
    black_alonem text,
    asian_alonee text,
    asian_alonem text,
    hispanic_totale text,
    hispanic_totalm text,
    median_incomee text,
    median_incomem text,
    poverty_totale text,
    poverty_totalm text,
    poverty_belowe text,
    poverty_belowm text,
    total_householdse text,
    total_householdsm text,
    no_vehiclee text,
    no_vehiclem text,
    pop_25_pluse text,
    pop_25_plusm text,
    bachelors_pluse text,
    bachelors_plusm text,
    pct_black text,
    pct_white text,
    pct_hispanic text,
    pct_poverty text,
    pct_no_vehicle text,
    pct_bachelors text,
    high_moe_flag text,
    z_pct_black text,
    z_pct_poverty text,
    z_pct_no_vehicle text,
    vulnerability_index text,
    vulnerability_category text
);

-- note: import using psql command line
-- \copy demographics_tract from 'montgomery_demographics_tract.csv' delimiter ',' csv header;


-- cleaned tract demographics with proper data types
-- converts text fields to appropriate numeric types for analysis

drop table if exists demographics_tract_clean cascade;
create table demographics_tract_clean as
select 
    geoid as geoid,
    name as name,
    nullif(total_pope, 'NA')::integer as total_pop,
    nullif(pct_black, 'NA')::double precision as pct_black,
    nullif(pct_white, 'NA')::double precision as pct_white,
    nullif(pct_hispanic, 'NA')::double precision as pct_hispanic,
    nullif(pct_poverty, 'NA')::double precision as pct_poverty,
    nullif(pct_no_vehicle, 'NA')::double precision as pct_no_vehicle,
    nullif(pct_bachelors, 'NA')::double precision as pct_bachelors,
    nullif(median_incomee, 'NA')::integer as median_income,
    nullif(vulnerability_index, 'NA')::double precision as vulnerability_score,
    vulnerability_category,
    nullif(high_moe_flag, 'NA')::integer as high_moe_flag
from demographics_tract;

alter table demographics_tract_clean add primary key (geoid);


-- tract-level vulnerability index
-- recalculated using complete poverty data from tract level

drop table if exists vulnerability_index_tract cascade;
create table vulnerability_index_tract as
select 
    geoid,
    (pct_black - avg(pct_black) over()) / nullif(stddev(pct_black) over(), 0) as z_pct_black,
    (pct_poverty - avg(pct_poverty) over()) / nullif(stddev(pct_poverty) over(), 0) as z_pct_poverty,
    (pct_no_vehicle - avg(pct_no_vehicle) over()) / nullif(stddev(pct_no_vehicle) over(), 0) as z_pct_no_vehicle,
    (coalesce((pct_black - avg(pct_black) over()) / nullif(stddev(pct_black) over(), 0), 0) + 
     coalesce((pct_poverty - avg(pct_poverty) over()) / nullif(stddev(pct_poverty) over(), 0), 0) + 
     coalesce((pct_no_vehicle - avg(pct_no_vehicle) over()) / nullif(stddev(pct_no_vehicle) over(), 0), 0)) / 3.0 as vulnerability_score,
    case 
        when (coalesce((pct_black - avg(pct_black) over()) / nullif(stddev(pct_black) over(), 0), 0) + 
              coalesce((pct_poverty - avg(pct_poverty) over()) / nullif(stddev(pct_poverty) over(), 0), 0) + 
              coalesce((pct_no_vehicle - avg(pct_no_vehicle) over()) / nullif(stddev(pct_no_vehicle) over(), 0), 0)) / 3.0 > 1.0 then 'High'
        when (coalesce((pct_black - avg(pct_black) over()) / nullif(stddev(pct_black) over(), 0), 0) + 
              coalesce((pct_poverty - avg(pct_poverty) over()) / nullif(stddev(pct_poverty) over(), 0), 0) + 
              coalesce((pct_no_vehicle - avg(pct_no_vehicle) over()) / nullif(stddev(pct_no_vehicle) over(), 0), 0)) / 3.0 > 0.0 then 'Moderate'
        when (coalesce((pct_black - avg(pct_black) over()) / nullif(stddev(pct_black) over(), 0), 0) + 
              coalesce((pct_poverty - avg(pct_poverty) over()) / nullif(stddev(pct_poverty) over(), 0), 0) + 
              coalesce((pct_no_vehicle - avg(pct_no_vehicle) over()) / nullif(stddev(pct_no_vehicle) over(), 0), 0)) / 3.0 > -1.0 then 'Low'
        else 'Very Low'
    end as vulnerability_category
from demographics_tract_clean
where pct_black is not null 
  and pct_poverty is not null
  and pct_no_vehicle is not null;

alter table vulnerability_index_tract add primary key (geoid);