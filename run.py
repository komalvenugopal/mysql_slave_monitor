#!/usr/bin/env python
#RUN */5 * * * * python /opt/mysql_montior/run.py

import yaml
import logging
import datetime
import os
from checkers.replication import ReplicationChecker

if __name__ == '__main__':
    directory = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    config = yaml.load((open(os.path.join(directory, 'config.yml'), 'r').read()))

    logging.basicConfig(filename=os.path.join(directory, 'replication.log'),level=logging.DEBUG)
    logging.info('Checker started at: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    checker = ReplicationChecker(
        project_directory=directory,
        lag_interval=300,
        lag_duration=1800,
        user=config['mysql']['user'],
        password=config['mysql']['password'],
        host=config['mysql']['host'],
        port=config['mysql']['port'],
        notifiers=config['notifiers']
    )
    
    checker.check()
    logging.info('Checker ended at: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
