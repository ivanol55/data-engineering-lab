INSERT INTO roles (role_id, name, description) VALUES
    (1, 'admin',      'Full administrative access'),
    (2, 'engineer',   'Builds and operates internal services'),
    (3, 'analyst',    'Reads business and security data'),
    (4, 'support',    'Handles customer accounts'),
    (5, 'contractor', 'Time-limited external collaborator');

WITH seed AS (
    SELECT
        i,
        (ARRAY['Avery','Marta','Noah','Priya','Lucas','Sofia','Kenji','Amara',
               'Elena','Omar','Ingrid','Mateo','Zara','Felix','Nadia','Hugo',
               'Leila','Tomas','Yuna','Ravi'])[1 + (i % 20)] AS first_name,
        (ARRAY['Chen','Silva','Kowalski','Nair','Fischer','Rossi','Tanaka',
               'Okafor','Petrova','Haddad','Larsen','Garcia','Khan','Weber',
               'Novak','Moreau','Ali','Kovac','Park','Iyer'])[1 + ((i * 7) % 20)] AS last_name,
        (ARRAY['United States','United Kingdom','Germany','France','Netherlands',
               'Spain','Canada','Australia','Japan','Brazil','India','South Africa'])[1 + (i % 12)] AS country,
        (ARRAY['New York','London','Berlin','Paris','Amsterdam','Madrid',
               'Toronto','Sydney','Tokyo','Sao Paulo','Bengaluru','Cape Town'])[1 + (i % 12)] AS city,
        (ARRAY[40.7128, 51.5074, 52.5200, 48.8566, 52.3676, 40.4168,
               43.6532, -33.8688, 35.6762, -23.5505, 12.9716, -33.9249])[1 + (i % 12)] AS lat,
        (ARRAY[-74.0060, -0.1278, 13.4050, 2.3522, 4.9041, -3.7038,
               -79.3832, 151.2093, 139.6503, -46.6333, 77.5946, 18.4241])[1 + (i % 12)] AS lon,
        (ARRAY['Engineering','Security','Finance','Sales','Support','Legal','People'])[1 + (i % 7)] AS department,
        (now() - make_interval(days => 500 + ((i * 37) % 1300)))::timestamptz AS created_at
    FROM generate_series(1, 2000) AS i
), with_times AS (
    SELECT
        *,
        LEAST(
            now() - interval '1 hour',
            created_at + make_interval(days => ((i * 13) % 300), hours => ((i * 7) % 24))
        ) AS updated_at
    FROM seed
)
INSERT INTO users (
    user_id, email, full_name, role_id, account_status, department,
    home_country, home_city, home_lat, home_lon, mfa_enabled,
    created_at, updated_at, last_login_at, deleted_at
)
SELECT
    ('00000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    lower(first_name) || '.' || lower(last_name) || i || '@acme.example',
    first_name || ' ' || last_name,
    1 + (i % 5),
    CASE
        WHEN i % 47 = 0 THEN 'disabled'
        WHEN i % 20 = 0 THEN 'disabled'
        WHEN i % 20 = 1 THEN 'locked'
        WHEN i % 20 = 2 THEN 'suspended'
        ELSE 'active'
    END,
    department,
    country, city, lat, lon,
    (i % 5) <> 0,
    created_at,
    updated_at,
    CASE
        WHEN i % 47 = 0 THEN NULL
        WHEN i % 11 = 0 THEN now() - make_interval(days => 150 + (i % 120))
        WHEN i % 17 = 0 THEN NULL
        ELSE now() - make_interval(hours => (i * 19) % 720)
    END,
    CASE WHEN i % 47 = 0 THEN now() - make_interval(days => 5 + (i % 20)) END
FROM with_times;

ANALYZE users;
ANALYZE roles;
