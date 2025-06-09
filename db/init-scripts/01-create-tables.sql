-- Create enum type for message types
CREATE TYPE messagetype AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');

-- Create leads table first
CREATE TABLE IF NOT EXISTS leads (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create chat_messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR PRIMARY KEY,
    lead_id VARCHAR NOT NULL,
    message_type messagetype NOT NULL,
    content TEXT NOT NULL,
    stage VARCHAR,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

-- Create recommendation_sets table
CREATE TABLE IF NOT EXISTS recommendation_sets (
    id VARCHAR PRIMARY KEY,
    lead_id VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    selected_recommendation VARCHAR,
    selection_timestamp TIMESTAMP WITH TIME ZONE,
    reasoning TEXT,
    next_steps JSONB,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

-- Create product_recommendations table
CREATE TABLE IF NOT EXISTS product_recommendations (
    id VARCHAR PRIMARY KEY,
    recommendation_set_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT NOT NULL,
    price FLOAT NOT NULL,
    features JSONB NOT NULL,
    benefits JSONB NOT NULL,
    suitability_score FLOAT NOT NULL,
    customization_options JSONB,
    FOREIGN KEY (recommendation_set_id) REFERENCES recommendation_sets(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_lead_id ON chat_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_recommendation_sets_lead_id ON recommendation_sets(lead_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_set_id ON product_recommendations(recommendation_set_id);