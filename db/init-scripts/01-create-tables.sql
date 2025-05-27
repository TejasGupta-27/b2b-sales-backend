-- Create enum type for message types
CREATE TYPE messagetype AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');

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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_lead_id ON chat_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at); 