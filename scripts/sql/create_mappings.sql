

-- precinct name mappings derived from python analysis of election data
-- establishes relationship between 2024 and 2020 precinct naming conventions
-- enables accurate year-over-year turnout comparisons

-- clear existing mapping data before inserting new records
truncate precinct_name_mapping;

-- insert 2024 to 2020 precinct name correspondences (41 matched pairs)
-- mapping determined through manual comparison of precinct boundaries and locations
insert into precinct_name_mapping (name_2024, name_2020) values
('101 WILSON COMM & ATHLETIC CTR', 'AFED Conference Ctr'),
('102 VAUGHN PARK CH', 'Vaughn Park Church of Christ'),
('103 MUSEUM OF FINE ARTS', 'Museum of Fine Arts'),
('104 WHITFIELD METHODIST', 'Whitfield UMC'),
('105 ALDERSGATE METHODIST', 'Aldersgate UMC'),
('106 CITY OF REFUGE CH', 'City of Refuge Church'),
('107 TRENHOLM COMM COLLEGE', 'Trenholm St Comm College'),
('201 ST PAUL AME CH', 'St Paul AME Church'),
('202 BEULAH BAPT CH', 'Beulah Baptist'),
('203 HAYNEVILLE RD COMM CTR', 'Hayneville Rd Comm Ctr'),
('205 SOUTHLAWN BAPT', 'Southlawn Baptist'),
('207 HUNTER STATION CC', 'Hunter Station Comm Ctr'),
('209 1ST SOUTHERN BAPT', 'First Southern Baptist'),
('210 PINTLALA FIRE DEPT', 'Pintlala VFD'),
('211 RUFUS LEWIS LIBRARY', 'Rufus Lewis Library'),
('212 MACEDONIA BAPT CH', 'Macedonia Miracle Worship Ctr'),
('301 DALRAIDA CH CHRIST', 'Dalraida Church of Christ'),
('302 EASTERN HILLS BAPT', 'Eastern Hills Baptist'),
('303 EASTMONT BAPT CH', 'Eastmont Baptist'),
('305 FRAZER CHURCH', 'Frazer UMC'),
('306 EASTDALE BAPT CH', 'Eastdale Baptist'),
('401 ST_ JAMES BAPT CH', 'St James Baptist'),
('402 MCINTYRE CC', 'McIntyre Comm Ctr'),
('403 CLEVELAND AVE YMCA', 'Cleveland Ave YMCA'),
('404 ASU ACADOME', 'AL State University Acadome'),
('405 HOUSTON HILLS CC', 'Houston Hills Comm Ctr'),
('406 NEWTOWN COMM CTR', 'Newtown Comm Ctr'),
('408 HIGHLAND GARDEN CC', 'Highland Gardens Comm Ctr'),
('409 BETTER COVENANT MINS', 'Covenant Ministries'),
('411 UNION ACADEMY BAPT', 'Union Academy Baptist'),
('412 UNION CHAPEL AME', 'Union Chapel AME Church'),
('413 PASSION CH MONTGOMERY', 'Passion Church Montgomery'),
('501 1ST CHRISTIAN CH', 'First Christian Church'),
('502 SNOWDOUN VFD', 'Snowdoun Women''s Club'),
('503 LAPINE BAPT CH', 'Lapine Baptist'),
('504 RAMER PUBLIC LIBRARY', 'Ramer Library'),
('506 DAVIS CROSSRODS', 'Davis Crossroads Fire St'),
('507 DUBLIN SO MO VFD', 'Dublin Fire St'),
('508 PINE LEVEL SO MO VFD', 'Pine Level Fire St'),
('509 WOODLAND UN METHODIST', 'Woodland UMC'),
('512 ST JAMES METHODIST', 'St James UMC');

-- precinct to polling place location mapping
-- connects 2020 precinct names to specific polling place facilities
-- used for distance calculations and spatial analysis
truncate precinct_polling_map;

insert into precinct_polling_map (precinct_2020_name, polling_place_id, polling_name) values
('AFED Conference Ctr', 6, 'AFED Conference Center'),
('Vaughn Park Church of Christ', 37, 'Vaughn Park Church of Christ'),
('Museum of Fine Arts', 38, 'Montgomery Museum of Fine Arts'),
('Whitfield UMC', 34, 'Whitfield Methodist Church'),
('Aldersgate UMC', 35, 'Aldersgate Methodist Church'),
('City of Refuge Church', 31, 'City of Refuge Church'),
('Trenholm St Comm College', 13, 'Drum Theater / Huntingdon College'),
('St Paul AME Church', 7, 'St. Paul AME Church'),
('Beulah Baptist', 8, 'Beulah Baptist Church'),
('Hayneville Rd Comm Ctr', 11, 'Hayneville Road Community Center'),
('Southlawn Baptist', 4, 'Southlawn Baptist Church'),
('Hunter Station Comm Ctr', 20, 'Hunter Station Community Center'),
('First Southern Baptist', 3, 'First Southern Baptist Church'),
('Pintlala VFD', 1, 'Pintlala Fire Department'),
('Rufus Lewis Library', 10, 'Rufus Lewis Library'),
('Macedonia Miracle Worship Ctr', 24, 'Sheridan Heights Community Center'),
('Dalraida Church of Christ', 45, 'Dalraida Church of Christ'),
('Eastern Hills Baptist', 42, 'Eastern Hills Baptist Church'),
('Eastmont Baptist', 44, 'Eastmont Baptist Church'),
('Frazer UMC', 43, 'Frazer United Methodist Church'),
('Eastdale Baptist', 46, 'Eastdale Baptist Church'),
('St James Baptist', 9, 'St. James Baptist Church'),
('McIntyre Comm Ctr', 14, 'McIntyre Community Center'),
('Cleveland Ave YMCA', 15, 'Cleveland Ave. YMCA'),
('AL State University Acadome', 16, 'Alabama State University / Acadome'),
('Houston Hills Comm Ctr', 17, 'Houston Hills Community Center'),
('Newtown Comm Ctr', 21, 'Newtown Community Center'),
('Highland Gardens Comm Ctr', 22, 'Highland Gardens Community Center'),
('Covenant Ministries', 23, 'Chisholm Community Center'),
('Union Academy Baptist', 25, 'Union Academy Baptist Church'),
('Union Chapel AME Church', 49, 'Union Chapel AME Church'),
('Passion Church Montgomery', 47, 'Passion Church - Montgomery'),
('First Christian Church', 39, 'First Christian Church'),
('Snowdoun Women''s Club', 2, 'Snowdoun Volunteer Fire Department'),
('Lapine Baptist', 18, 'Lapine Baptist Church'),
('Ramer Library', 27, 'Ramer Public Library'),
('Davis Crossroads Fire St', 29, 'Davis Crossroads Fire Station'),
('Dublin Fire St', 26, 'Dublin Fire Station'),
('Pine Level Fire St', 28, 'Pine Level Fire Station'),
('Woodland UMC', 32, 'Woodland United Methodist Church'),
('St James UMC', 36, 'St. James United Methodist Church');