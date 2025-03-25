ARG BUILD_FROM
FROM $BUILD_FROM

# Install only essential dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip

# Ensure pip is up to date with minimal intervention
RUN python3 -m pip install --upgrade pip --user

# Set working directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
COPY main.py .
COPY run.sh /

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Make run script executable
RUN chmod a+x /run.sh

# Set the entrypoint
CMD [ "/run.sh" ]
