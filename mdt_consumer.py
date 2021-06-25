# -*- coding: utf-8 -*-

from socket import timeout
import sys
import os
import shutil
import json

import logging
import logging.config

from argparse import ArgumentParser
from configparser import ConfigParser, ExtendedInterpolation

from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin

# config = ConfigParser(interpolation=ExtendedInterpolation(), allow_no_value=True)
# here = os.path.dirname(os.path.abspath(__file__))
# log_path = here + "/config/config.ini"
# config.read(log_path)


APP_NAME = "mdt-consumer"

here = os.path.dirname(os.path.abspath(__file__))

# Creating app folder
if not os.path.exists(f"/etc/opt/{APP_NAME}/"):
    os.mkdir(f'/etc/opt/{APP_NAME}/')

# Copy default logging configuration file
if not os.path.isfile(f"/etc/opt/{APP_NAME}/logconfig.ini"):
    shutil.copy(here + "/config/logconfig.ini", f'/etc/opt/{APP_NAME}/')

# Copy default configuration file
if not os.path.isfile(f"/etc/opt/{APP_NAME}/config.ini"):
    shutil.copy(here + "/config/config.ini", f'/etc/opt/{APP_NAME}/')

# Creating logs folder
if not os.path.exists(f"/var/log/{APP_NAME}/"):
    os.mkdir(f'/var/log/{APP_NAME}/')

# Logging config file
logging.config.fileConfig(f"/etc/opt/{APP_NAME}/logconfig.ini")
logger = logging.getLogger()

# Config file
config = ConfigParser(interpolation=ExtendedInterpolation(), allow_no_value=True)
config.read(f"/etc/opt/{APP_NAME}/config.ini")

rabbit_ip = config.get("RABBITMQ", "ip")
rabbit_port = config.getint("RABBITMQ", "port")
rabbit_vhost = config.get("RABBITMQ", "vhost")
rabbit_user = config.get("RABBITMQ", "user")
rabbit_passw = config.get("RABBITMQ", "password")

consume_queues = []
for exchange_name in json.loads(config["RABBITMQ"]["exchanges"]):
    consume_queues.append(
        Queue(
            f"mdt_consumer_{exchange_name}",
            Exchange(exchange_name,
                     type="topic",
                     durable=False),
            routing_key=f"{exchange_name}.#",
            durable=False,
            exclusive=False)
    )


class Worker(ConsumerMixin):
    def __init__(self, connection, queues):
        self.connection = connection
        self.queues = queues

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues,
                         callbacks=[self.on_message])]

    def on_message(self, body, message):
        # from exchange: actions queue: player_actions
        try:
            routing_key = message.delivery_info['routing_key']
            exchange_name = message.delivery_info['exchange']
            print_body = config.getboolean("VERBOSE", "print_body_messages")
            body_message = json.loads(body) if print_body else ""
            logger.info(f"Received:\n {routing_key}\n {exchange_name}\n{body_message}")
        except BaseException:
            # Do nothing
            logger.info(
                'a non-valid message has been received, \
                info:\n {0}'.format(message.delivery_info))

        # print json.dumps(message)
        message.ack()


def start():
    # Create exchanges and queues to aply at connection
    try:
        with Connection(hostname=rabbit_ip,
                        port=rabbit_port,
                        userid=rabbit_user,
                        password=rabbit_passw,
                        virtual_host=rabbit_vhost,
                        heartbeat=4) as conn:
            conn.ensure_connection(max_retries=2, timeout=5)
            worker = Worker(conn, consume_queues)
            logger.info(f"=={APP_NAME}== waiting for messages.....")
            worker.run()
    except BaseException:
        logger.error(
            'AMQP connection failed, \
                \n ip: {0} \
                \n port: {1}'.format(rabbit_ip,
                                     rabbit_port))
        exit()


def main():
    argp = ArgumentParser(
        description='An AMQP Consumer',
        epilog='Pablo Salva Garcia (UWS)')

    argp.add_argument(
        '--start',
        action="store_true",
        help='start the AMQP consumer')

    arguments = argp.parse_args()

    if arguments.start:
        logger.info('The mdt-consumer is going to start')
        start()


if __name__ == "__main__":
    logger.info('The mdt-consumer is in main')
    main()
