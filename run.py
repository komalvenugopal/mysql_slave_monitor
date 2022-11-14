#!/usr/bin/env python
#RUN */5 * * * * python /opt/mysql_montior/run.py

import yaml
import logging
import datetime
import os
from checkers.replication import ReplicationChecker

if __name__ == '__main__':
    directory = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    config = yaml.load(open(os.path.join(directory, 'config.yml'), 'r').read(),Loader=yaml.Loader)

    logging.basicConfig(filename=os.path.join(directory, 'replication.log'),level=logging.DEBUG)
    logging.info('Checker started at: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    for host in config['mysql']['hosts']:
        checker = ReplicationChecker(
            host=host,
            user=config['mysql']['user'],
            password=config['mysql']['password'],
            port=config['mysql']['port'],
            project_directory=directory,
            lag_interval=300,
            lag_duration=1800,
            notifiers=config['notifiers']
        )
        checker.check()
        logging.info("Checker ended at" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ "for " + host)