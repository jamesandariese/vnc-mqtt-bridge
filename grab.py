import base64
import hashlib
import logging
import json
import os
import sys
import time
import traceback

import imageio

from vncdotool import api
from twisted.internet import reactor

import paho.mqtt.client as paho

# LOGGING

# setup logging to console
class SkipLevelsFilter(logging.Filter):
    def __init__(self, skip_levels=[]):
        self.skip_levels = skip_levels

    def filter(self, rec):
        return rec.levelno not in self.skip_levels


logger = logging.getLogger('keywords_pipeline')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# stderr for >=ERROR
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)
stderr_handler.setFormatter(formatter)

# stdout for everything but ERROR.
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.addFilter(SkipLevelsFilter([logging.ERROR]))
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

# attach the handlers and set the default level to DEBUG for the remainder of the logger setup
logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)
logger.setLevel(logging.DEBUG)

# now extract the desired loglevel or use INFO if not specified, DEBUG is still the _active_ level though
# so if anything fails here, it will be logged even if it's a debug message
LOGLEVEL = os.getenv('LOGLEVEL') or "INFO"
numeric_level = getattr(logging, LOGLEVEL.upper(), None)
if not isinstance(numeric_level, int):
    logger.critical('Invalid log level: %s' % LOGLEVEL)
    os.exit(78)
# here's the debug message which will be logged before changing the level.
logger.debug(f'setting loglevel to {LOGLEVEL}')
logger.setLevel(numeric_level)

# END LOGGING

MQTT_USER=os.environ['MQTT_USER']
MQTT_PASSWORD=os.environ['MQTT_PASSWORD']
MQTT_HOST=os.environ['MQTT_HOST']
VNC_HOST=os.environ['VNC_HOST']
VNC_PASSWORD=os.environ['VNC_PASSWORD']
MQTT_TOPIC=os.environ['MQTT_TOPIC']
DEVICE_NAME=os.environ.get('DEVICE_NAME', None)
DEVICE_ID=os.environ.get('DEVICE_ID', None)
INTERVAL=float(os.environ.get('INTERVAL', '5'))

SANITIZED_HOST=VNC_HOST.replace('.','_')
NAME=DEVICE_NAME or SANITIZED_HOST
DEVICE_ID = DEVICE_ID or SANITIZED_HOST
OBJECT_ID = base64.b32encode(hashlib.sha1(NAME.encode('utf-8')).digest()).decode('utf-8')

def blackwhite(imgf):
    r = imageio.read(imgf)
    screen = r.get_data(0).flatten()
    byt = screen.tobytes()
    count = len(byt)

    blackcount = byt.count(b'\x00')
    whitecount = byt.count(b'\xff')
    return blackcount,whitecount,count

mqtt_clients = []
def mqtt():
    if len(mqtt_clients) > 0:
        c = mqtt_clients[0]
        try:
            c.publish(f"homeassistant/camera/{DEVICE_ID}/config", json.dumps({
              "name": NAME,
              "topic": MQTT_TOPIC + "/image",
              "unique_id": DEVICE_ID+"-T",
              "device_class": "camera",
              "device": {
                "identifiers": DEVICE_ID,
                "manufacturer": "VNC-MQTT",
                "model": "v0.1",
              },
            }), retain=True)
            return mqtt_clients[0]
        except:
            try:
                mqtt_clients[0].loop_stop()
            except:
                pass
            mqtt_clients.clear()
            return mqtt()
    try:
        logger.info("Connecting to MQTT")
        c = paho.Client()
        c.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        c.connect(MQTT_HOST)
        c.loop_start()
        mqtt_clients.append(c)
    except Exception as e:
        logger.error(traceback.format_exc())
        time.sleep(1)
    return mqtt()

t = None

vnc_clients = []
def vnc():
    if len(vnc_clients) > 0:
        try:
            vnc_clients[0].refreshScreen()
            # this is the only path out.  an existing vnc client
            # that successfully refreshes its screen
            return vnc_clients[0]
        except:
            vnc_clients.clear()
    try:
        logger.info("Connecting to VNC")
        vnc_clients.append(api.connect(VNC_HOST, VNC_PASSWORD))
    except Exception as e:
        logger.error(traceback.format_exc())
        time.sleep(1)
    return vnc()

while True:
    if t is None:
        t = time.time()
    try:
        logger.debug("refreshing for capture")
        vnc().refreshScreen()
        logger.debug("capturing")
        vnc().captureScreen('capture.png')
        logger.debug("publishing to mqtt")
        with open('capture.png', 'rb') as f:
            capture = f.read()
        (black,white,total) = blackwhite('capture.png')
        if black > (total * .95): # if it's more than 95% black, it's a failure
            logger.warning(f"screen is more than 95% black.  considering as failure.")
            continue
        if white > (total * .95): # if it's more than 95% white, it's a failure
            logger.warning(f"screen is more than 95% white.  considering as failure.")
            continue
        with open('capture.time', 'wb') as f:
            pass  # touch :D

        p = mqtt().publish(topic=MQTT_TOPIC + "/image", payload=capture)
    except Exception as e:
        logger.error(traceback.format_exc())
    time_left = INTERVAL - (time.time() - t)
    if time_left > 0:
        logger.debug(f"sleeping for {time_left}s")
        time.sleep(time_left)
    else:
        logger.warning(f"interval missed ({0-time_left}s overdue)")
    t = None

mqtt().loop_end()
reactor.stop()
