-- Database Setup Script for Enterprise Data Lineage Platform
-- Run this script as the postgres superuser

-- Create the database
CREATE DATABASE lineage_platform;

-- Connect to the database (you'll need to do this manually in psql or pgAdmin)
-- \c lineage_platform

-- Create the user
CREATE USER lineage_user WITH PASSWORD 'password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE lineage_platform TO lineage_user;

-- Grant schema privileges (needed for PostgreSQL 15+)
\c lineage_platform
GRANT ALL ON SCHEMA public TO lineage_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lineage_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lineage_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO lineage_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO lineage_user;
