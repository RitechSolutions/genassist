

#!/bin/bash

# Set error handling to stop on errors
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER genassist_read WITH PASSWORD 'genassist_read';
    GRANT pg_read_all_data to genassist_read;

    CREATE USER metabase_admin WITH PASSWORD 'metabase_admin';

    CREATE DATABASE "metabase_db" WITH OWNER "metabase_admin" ENCODING 'UTF8';
    GRANT ALL PRIVILEGES ON DATABASE "metabase_db" TO "metabase_admin";
EOSQL
