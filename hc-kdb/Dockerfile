# Use a lightweight Linux base image
FROM ubuntu:20.04

# Suppress interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install any dependencies kdb+ needs (e.g., libssl, etc.)
RUN apt-get update && \
    apt-get install -y \
    wget \
    libssl-dev \
    libmariadb-dev-compat \
    libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

# Create a directory for kdb+
RUN mkdir -p /opt/kdb

# Copy kdb+ binary and license into container
# Make sure you have these files locally (replace with your actual paths)
COPY l64arm/l64arm/q /opt/kdb/q
COPY l64arm/q.k /opt/kdb/q.k

# Ensure the kdb+ binary is executable
RUN chmod +x /opt/kdb/q

# Set environment variables
ENV QHOME=/opt/kdb
ENV PATH=$QHOME:$PATH

# Expose the default kdb+ port
EXPOSE 5000

# By default, run q with no arguments
CMD ["/opt/kdb/q"]