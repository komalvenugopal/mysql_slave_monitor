import mysql.connector
import datetime
import os
import time
import logging
import json
import boto3
import requests

class ReplicationChecker(object):
    def __init__(self, project_directory, lag_interval, lag_duration, user, password, host='local', port=3306,notifiers={}):
        self.project_directory = project_directory
        self.lag_interval = lag_interval
        self.lag_duration = lag_duration
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.messages = []
        self.notifiers=notifiers

        self.LAG_LOCK = os.path.join(self.project_directory, 'lag.lock')
        self.WARNING_LOCK = os.path.join(self.project_directory, 'warning.lock')
        self.DANGER_LOCK = os.path.join(self.project_directory, 'danger.lock')

    def check(self):
        try:
            cnx = mysql.connector.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            logging.debug('Conected to MYSQL')
            cursor = cnx.cursor()
            query = 'SHOW SLAVE STATUS;'

            cursor.execute(query)
            replication_status_row = cursor.fetchall()[0]
            last_error_no = replication_status_row[18]
            last_error = replication_status_row[19]
            seconds_behind_master = replication_status_row[32]
            slave_sql_running_state = replication_status_row[10]

            logging.info('Last Error No: ' + str(last_error_no))
            logging.info('Last Error: ' + str(last_error_no))
            logging.info('Seconds behind master: ' + str(seconds_behind_master))
            logging.info('slave_sql_running_state: ' + str(slave_sql_running_state))

            if last_error_no != 0:
                self.raise_replication_error(last_error,slave_sql_running_state)
            elif seconds_behind_master >= self.lag_interval:
                self.track_lag(slave_sql_running_state, seconds_behind_master)
            else:
                self.confirm_normality()
        except Exception as error:
            self.raise_exception(error)
        if self.messages:
            self.trigger_notifications()

    def raise_replication_error(self, last_error, slave_sql_running_state):
        self.messages.append({
            'status': 'danger',
            'short_message': 'Replication Error',
            'long_message': last_error + 'Current state: %s' % slave_sql_running_state,
            'time_string': datetime.datetime.now().isoformat()
        })
        self.write_lock('danger')

    def track_lag(self, slave_sql_running_state, seconds_behind_master):
        logging.debug('There is a lag of more than lag_interval seconds')
        if os.path.isfile(self.LAG_LOCK):
            if not os.path.isfile(self.WARNING_LOCK):
                with open(self.LAG_LOCK, 'r') as f:
                    timestamp = int(f.read())
                    current_timestamp = int(time.time())
                    difference = current_timestamp - timestamp
                    if difference >= self.lag_duration:
                        self.raise_lag_warning(slave_sql_running_state,seconds_behind_master)
                    else:
                        logging.debug("Hasn't been lagging for more than lag_interval set. Still Cool.")
        else:
            self.write_lock('lag')

    def raise_lag_warning(self, slave_sql_running_state, seconds_behind_master):
        self.messages.append({
            'status': 'warning',
            'short_message': 'Replication Lag',
            'long_message':
                'The replica is lagging more than %s seconds'
                'behind master for longer than %s seconds. Current state: %s. '
                'Current lag: %s seconds.'
                % (str(self.lag_interval), str(self.lag_duration),
                   slave_sql_running_state, seconds_behind_master),
            'time_string':
                datetime.datetime.now().isoformat()
        })
        self.write_lock('warning')
        logging.warn('The lag has lasted longer than 5 minutes.')

    def confirm_normality(self):
        if os.path.isfile(self.DANGER_LOCK) or os.path.isfile(
                self.WARNING_LOCK):
            self.messages.append({
                'status': 'good',
                'short_message': 'Everything is back to normal',
                'long_message':
                    'Nothing to complain about.',
                'time_string':
                    datetime.datetime.now().isoformat()
            })
        self.clear_locks()
        logging.info('Everything is OK!')

    def raise_exception(self, error):
        self.messages.append({
            'status': 'danger',
            'short_message': 'Exception',
            'long_message': str(error),
            'time_string': datetime.datetime.now().isoformat()
        })
        self.write_lock('danger')

    def clear_locks(self):
        if os.path.isfile(self.DANGER_LOCK):
            os.remove(self.DANGER_LOCK)
        if os.path.isfile(self.LAG_LOCK):
            os.remove(self.LAG_LOCK)
        if os.path.isfile(self.WARNING_LOCK):
            os.remove(self.WARNING_LOCK)

    def write_lock(self, status):
        file_path = os.path.join(self.project_directory, status + '.lock')
        if not os.path.isfile(file_path):
            with open(file_path, 'w') as f:
                f.write(str(int(time.time())))

    def trigger_notifications(self):
        lambda_client = boto3.client('lambda')
        for message in self.messages:
            long_message = message['long_message']
            status = message['status']
            short_message = message['short_message']
            time_string = message['time_string']       

            for notifier in self.notifiers:
                if(notifier=="slack_url"):
                    message = self.construct_message(long_message, status, short_message, time_string)
                    request = requests.post(self.notifiers["slack_url"], data=message)
                elif(notifier=="lambda_function"):
                    lambda_payload = {
                        "name": short_message,
                        "state": status,
                        "message": long_message
                    }
                    lambda_client.invoke(FunctionName=self.notifiers["lambda_function"], InvocationType='Event', Payload=json.dumps(lambda_payload))            
        self.messages = []
        

    def construct_message(self, long_message, status, short_message, time_string):
        message = '''
            {
                "text": "%s",
                "attachments": [
                    {
                        "pretext":"",
                        "color": "%s",
                        "fields": [
                            {
                                "title": "Message",
                                "value": "%s",
                                "short": true
                            },
                            {
                                "title": "Time",
                                "value": "%s",
                                "short": true
                            }
                        ]
                    }
                ]
            }
        ''' % (long_message, status, short_message, time_string)
        return message
