import asyncore
import threading
import time
import base64
import requests
import logging
import paho.mqtt.client as mqtt
import json
import traceback

# Configure more detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Comprehensive logging for debugging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/data/addon_debug.log'  # Log to a file for persistent debugging
)
logger = logging.getLogger(__name__)

# Enhanced config loading with extensive error handling
try:
    with open('/data/options.json', 'r') as config_file:
        config = json.load(config_file)
except Exception as e:
    logger.critical(f"CRITICAL: Failed to load configuration file: {e}")
    logger.critical(traceback.format_exc())
    config = {}

# Extract configuration with extensive logging
broker_address = config.get('mqtt_broker', '')
mqtt_username = config.get('mqtt_user', '')
mqtt_password = config.get('mqtt_pass', '')
sms_uri = config.get('sms_uri', '')
sms_credentials = config.get('sms_credentials', '')
alarm_send_delay_minutes = config.get('alarm_delay_minutes', 5)
alarm_send_delay = alarm_send_delay_minutes * 60

# Parsing configuration with detailed logging
try:
    cold_room_sensors = [s.strip() for s in config.get('cold_room_sensors', '').split(',') if s.strip()]
    normal_room_sensors = [s.strip() for s in config.get('normal_room_sensors', '').split(',') if s.strip()]
    phone_numbers = [s.strip() for s in config.get('phone_numbers', '').split(',') if s.strip()]
    
    logger.info(f"Loaded Configuration:")
    logger.info(f"Cold Room Sensors: {cold_room_sensors}")
    logger.info(f"Normal Room Sensors: {normal_room_sensors}")
    logger.info(f"Phone Numbers: {phone_numbers}")
except Exception as e:
    logger.error(f"Configuration Parsing Error: {e}")
    logger.error(traceback.format_exc())
    cold_room_sensors = []
    normal_room_sensors = []
    phone_numbers = []

last_alarm_sent_time = 0

# In-memory alarm tracking with logging
alarms = {}



list_of_cold_room_sensors = cold_room_sensors
list_of_normal_room_sensors = normal_room_sensors

def send_mqtt(topic):
    try:
        logger.debug(f"Attempting to send MQTT message to topic: {topic}")
        client = mqtt.Client("P1")
        client.username_pw_set(username=mqtt_username, password=mqtt_password)
        client.connect(broker_address)
        client.publish(str(topic), "1")
        logger.info(f"MQTT message successfully published to topic '{topic}'")
    except Exception as e:
        logger.error(f"MQTT Publish Error: {e}")
        logger.error(traceback.format_exc())

def send_http_request(credentials, url, method, request_body, timeout):
    logger.debug(f"Preparing HTTP request to {url}")
    
    try:
        base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64_credentials}'
        }

        if method.upper() == 'POST':
            logger.debug(f"Sending POST request to {url}")
            logger.debug(f"Request Headers: {headers}")
            logger.debug(f"Request Body: {request_body}")
            
            response = requests.post(url, headers=headers, json=request_body, timeout=timeout)
            
            logger.debug(f"Response Status Code: {response.status_code}")
            logger.debug(f"Response Content: {response.text}")
            
            response.raise_for_status()
            return response.json()
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            raise ValueError("Only POST method is supported for SMS.")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request Error: {e}")
        logger.error(f"Request Details: URL={url}, Method={method}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Unexpected HTTP Request Error: {e}")
        logger.error(traceback.format_exc())
        return None

def send_sms(message, number):
    logger.info(f"Initiating SMS send to number: {number}")
    
    # Validate configuration
    if not all([sms_uri, sms_credentials, number]):
        logger.error("SMS sending failed: Missing configuration")
        logger.error(f"SMS URI: {bool(sms_uri)}, Credentials: {bool(sms_credentials)}, Number: {bool(number)}")
        return False

    body = {
        "to": number,
        "content": message
    }
    
    try:
        result = send_http_request(sms_credentials, sms_uri, 'POST', body, 100)
        
        if result:
            logger.info(f"SMS successfully sent to {number}")
            return True
        else:
            logger.warning(f"SMS sending failed for number {number}")
            return False
    
    except Exception as e:
        logger.error(f"Exception in SMS sending to {number}: {e}")
        logger.error(traceback.format_exc())
        return False

def drop_row(sensorid):
    if sensorid in alarms:
        del alarms[sensorid]
        logger.info(f"Alarm entry for sensor {sensorid} has been dropped")

def assign_to_memory(TypeOfAlarm, sensorid, Gatewayid, value, alarm_time):
    global last_alarm_sent_time

    current_time = time.time()
    logger.debug(f"Checking alarm cooldown: Current time {current_time}, Last alarm time {last_alarm_sent_time}")
    
    if current_time - last_alarm_sent_time < alarm_send_delay:
        logger.info(f"Alarm send delayed due to cooldown period for sensor {sensorid}")
        return

    last_alarm_sent_time = current_time

    if sensorid not in alarms:
        alarms[sensorid] = {
            'type': TypeOfAlarm,
            'gatewayid': Gatewayid,
            'value': value,
            'time': alarm_time,
            'sendstatus': "Not Sent"
        }

        alarm_message = (
            f' Alarm Alert! \\n'
            f'Alarm Case: {TypeOfAlarm} \\n'
            f'Sensor Id: {sensorid} \\n'
            f'Value: {value} \\n'
            f'Time: {alarm_time} \\n'
        )
        
        logger.info(f"Generated Alarm Message: {alarm_message}")
        
        if not phone_numbers:
            logger.error("No phone numbers configured for SMS alerts")
            return

        successful_sends = 0
        for num in phone_numbers:
            if send_sms(alarm_message, num):
                successful_sends += 1
        
        logger.info(f"SMS Alerts: {successful_sends} out of {len(phone_numbers)} sent successfully")
        
        # Sensor-specific handling with logging
        if sensorid in list_of_cold_room_sensors:
            logger.debug(f"Scheduling drop for cold room sensor {sensorid}")
            threading.Timer(5 * 60, drop_row, args=(sensorid,)).start()
        elif sensorid in list_of_normal_room_sensors:
            logger.debug(f"Scheduling drop for normal room sensor {sensorid}")
            threading.Timer(5 * 60, drop_row, args=(sensorid,)).start()

def convertdata(s):
    try:
        logger.debug(f"Converting incoming data: {s}")
        s = s.replace("\n", "").replace("b'", "").replace("\n\n'", "")
        outlist = s.split("}")
        
        # Detailed parsing with logging
        TypeOfAlarm = outlist[0].split(',')[0].split(":")[1].replace("\"", "")
        sensorid = outlist[4].split(',')[-1].split(":")[1].replace("\"", "")
        Gatewayid = outlist[4].split(',')[-2].split(":")[2].replace("\"", "")
        value = outlist[5].split(',')[4].replace("]]", "")
        alarm_time = outlist[5].split(',')[3].replace("]]", "").replace("[[", "").split("\"")[3]
        
        logger.info(f"Parsed Alarm Data: "
                     f"Type={TypeOfAlarm}, "
                     f"SensorID={sensorid}, "
                     f"GatewayID={Gatewayid}, "
                     f"Value={value}, "
                     f"Time={alarm_time}")
        
        assign_to_memory(TypeOfAlarm, sensorid, Gatewayid, value, alarm_time)
    except Exception as e:
        logger.error(f"Data Conversion Error: {e}")
        logger.error(f"Problematic Input: {s}")
        logger.error(traceback.format_exc())

class EchoHandler(asyncore.dispatcher_with_send):
    def handle_read(self):
        try:
            data = self.recv(8192)
            if data:
                logger.debug(f"Received data in EchoHandler: {data}")
                convertdata(str(data))
        except Exception as e:
            logger.error(f"EchoHandler Read Error: {e}")
            logger.error(traceback.format_exc())

class EchoServer(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        try:
            self.create_socket()
            self.set_reuse_addr()
            self.bind((host, port))
            self.listen(5)
            logger.info(f"Server initialized on host={host}, port={port}")
        except Exception as e:
            logger.critical(f"Server Initialization Error: {e}")
            logger.critical(traceback.format_exc())

    def handle_accepted(self, sock, addr):
        logger.info(f"Incoming connection from {addr}")
        try:
            handler = EchoHandler(sock)
        except Exception as e:
            logger.error(f"Error handling connection from {addr}: {e}")
            logger.error(traceback.format_exc())

def main():
    try:
        logger.info("Starting MQTT and SMS Monitoring Service")
        server = EchoServer('', 5060)
        logger.info("Server created successfully")
        asyncore.loop()
    except Exception as e:
        logger.critical(f"Critical Error in Main Execution: {e}")
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    main()
