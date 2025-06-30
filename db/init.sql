-- Initialize database for B2B Sales Backend
-- This script runs when the PostgreSQL container first starts

-- Create the database if it doesn't exist (this is handled by POSTGRES_DB env var)
-- The database 'b2b_sales' should already exist due to POSTGRES_DB=b2b_sales

-- Create extensions for advanced text search and similarity
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Configure text search settings
SET default_text_search_config = 'english';

-- Create a function to calculate text similarity
CREATE OR REPLACE FUNCTION similarity(text, text) RETURNS real AS $$
BEGIN
  RETURN pg_trgm.similarity($1, $2);
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- Create indexes that will be useful for our application
-- Note: Tables will be created by SQLAlchemy/Alembic, we're just setting up the database environment

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON DATABASE b2b_sales TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Set up default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;

-- Log successful initialization
DO $$
BEGIN
  RAISE NOTICE 'B2B Sales database initialized successfully';
END $$; 