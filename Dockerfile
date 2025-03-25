ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies and pip
RUN apk add --no-cache \
    python3 \
    python3-dev \
    py3-pip \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# Set Python environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Upgrade pip
RUN pip3 install --upgrade pip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir \
    --upgrade \
    --require-hashes \
    -r requirements.txt

# Copy application files
COPY main.py .
COPY run.sh /
RUN chmod a+x /run.sh

# Set the entrypoint
CMD [ "/run.sh" ]
