
import asyncore
import threading
import time
import base64
import requests
import logging
import paho.mqtt.client as mqtt
from sms import SMS
import json

# Load config from Home Assistant's options.json file
with open('/data/options.json', 'r') as config_file:
    config = json.load(config_file)

# Extract options
broker_address = config['mqtt_broker']
mqtt_username = config['mqtt_user']
mqtt_password = config['mqtt_pass']
sms_uri = config['sms_uri']
sms_credentials = config['sms_credentials']
alarm_send_delay_minutes = config['alarm_delay_minutes']
alarm_send_delay = alarm_send_delay_minutes * 60
cold_room_sensors = config['cold_room_sensors']
normal_room_sensors = config['normal_room_sensors']
phone_numbers = config['phone_numbers']

last_alarm_sent_time = 0


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ************************************************************************************************
def append_cold_list():
    # Hardcoded sensor IDs instead of reading from file
    new_list = [
        "62210229",
        "62240894",
        "06240840",
        "87654321",
        "12345678"
    ]
    return new_list

def append_normal_list():
    new_list = [
        "44443333",
        "66665555",
        "76543211",
        "88887777",
        "99998888"
    ]
    return new_list

list_of_cold_room_sensors = cold_room_sensors
list_of_normal_room_sensors = normal_room_sensors

# In-memory alarm tracking
alarms = {}

def send_mqtt(topic):
    try:
        client = mqtt.Client("P1")
        client.username_pw_set(username=mqtt_username, password=mqtt_password)
        client.connect(broker_address)
        client.publish(str(topic), "1")
        logger.info(f"MQTT Published to topic '{topic}'")
    except Exception as e:
        logger.error(f"MQTT error: {e}")

def send_http_request(credentials, url, method, request_body, timeout):
    base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {base64_credentials}'
    }

    try:
        if method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=request_body, timeout=timeout)
        else:
            raise ValueError("Only POST method is supported for SMS.")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP SMS error: {e}")
        return None

def send_sms(message, number):
    body = {
        "to": number,
        "content": message
    }
    try:
        result = send_http_request(sms_credentials, sms_uri, 'POST', body, 100)
        if result:
            logger.info(f"HTTP SMS sent to {number}")
        else:
            logger.warning(f"Failed to send HTTP SMS to {number}")
    except Exception as e:
        logger.error(f"Exception sending HTTP SMS: {e}")



def drop_row(sensorid):
    if sensorid in alarms:
        del alarms[sensorid]
        logger.info(f"Alarm for sensor {sensorid} dropped")


def assign_to_memory(TypeOfAlarm, sensorid, Gatewayid, value, alarm_time):
    global last_alarm_sent_time

    current_time = time.time()
    if current_time - last_alarm_sent_time < alarm_send_delay:
        logger.info("Delaying alarm send due to cooldown")
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
        numbers = ["01140214856", "01116072004", "01123008561"]
        for num in phone_numbers:
            send_sms(alarm_message, num)
        if sensorid in list_of_cold_room_sensors:
            threading.Timer(5 * 60, drop_row, args=(sensorid,)).start()
        elif sensorid in list_of_normal_room_sensors:
            threading.Timer(5 * 60, drop_row, args=(sensorid,)).start()


def convertdata(s):
    try:
        s = s.replace("\n", "").replace("b'", "").replace("\n\n'", "")
        outlist = s.split("}")
        TypeOfAlarm = outlist[0].split(',')[0].split(":")[1].replace("\"", "")
        sensorid = outlist[4].split(',')[-1].split(":")[1].replace("\"", "")
        Gatewayid = outlist[4].split(',')[-2].split(":")[2].replace("\"", "")
        value = outlist[5].split(',')[4].replace("]]", "")
        alarm_time = outlist[5].split(',')[3].replace("]]", "").replace("[[", "").split("\"")[3]
        assign_to_memory(TypeOfAlarm, sensorid, Gatewayid, value, alarm_time)
    except Exception as e:
        logger.error(f"Error converting data: {e}")

class EchoHandler(asyncore.dispatcher_with_send):
    def handle_read(self):
        data = self.recv(8192)
        if data:
            convertdata(str(data))

class EchoServer(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket()
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accepted(self, sock, addr):
        logger.info(f"Incoming connection from {addr}")
        handler = EchoHandler(sock)

server = EchoServer('', 5060)
asyncore.loop()
