#!/usr/bin/with-contenv bashio

# Log the start of the addon
bashio::log.info "Alarm Handler Addon starting..."

# Optional: You can load and log configuration values
MQTT_BROKER=$(bashio::config 'mqtt_broker')
bashio::log.info "MQTT Broker: ${MQTT_BROKER}"

# Run the Python script
python3 /app/main.py
