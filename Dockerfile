ARG BUILD_FROM
FROM $BUILD_FROM

# Set environment variables
ENV LANG C.UTF-8

# Install system dependencies and Python
RUN apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    build-base

# Set working directory
WORKDIR /app

# Copy application files
COPY main.py .
COPY run.sh /
COPY config.json /config.json

# Make run script executable
RUN chmod a+x /run.sh

# Install Python dependencies
RUN pip3 install
    paho-mqtt \
    influxdb \
    requests

# Set the entrypoint
CMD [ "/run.sh" ]
