FROM postgres:15

# Copy initialization scripts
COPY ./init-scripts/ /docker-entrypoint-initdb.d/

# Set environment variables
ENV POSTGRES_USER=myuser
ENV POSTGRES_PASSWORD=mypassword
ENV POSTGRES_DB=chat_db

# Expose PostgreSQL port
EXPOSE 5432 