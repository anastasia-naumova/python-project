import psycopg2
import time
import json
import sys

#разобраться с table_statuses

class Sensor:

    table_statuses = {}

    def __init__(self, command_line_arguments, db_name, db_user, db_password, db_host, db_port):
        if len(command_line_arguments) > 1:
            with open(format(command_line_arguments[1])) as f:
                file = f.read()
                self.config_file = json.loads(file)
        self.connection = psycopg2.connect(database=db_name, user=db_user, password=db_password, host=db_host,
                                           port=db_port)

    @staticmethod
    def compare_lists(list1, list2):
        i = 0
        if len(list1) == len(list2):
            while i < len(list1):
                if list1[i] in list2:
                    i += 1
                else:
                    print(False)
                    return False
            print(True)
            return True
        print(False)
        return False

    def get_cut_value_for_tables(self):
        cursor = self.connection.cursor()
        cut_value = {}
        for table in self.config_file['table_names']:
            cursor.execute("select cut_value from target_bookings.last_taken_data where job_name = %s and "
                           "table_name = %s", (self.config_file['job_name'], table))
            cut_value[table] = str(cursor.fetchone()[0])
        cursor.close()
        print(cut_value)
        return cut_value

    def check_table_status(self):
        cursor = self.connection.cursor()
        self.table_statuses = {}
        checking_table_updates = []
        cut_value = self.get_cut_value_for_tables()
        while time.time() - time_start < self.config_file['waiting_time'] and \
                self.compare_lists(self.config_file['table_names'], self.table_statuses.keys()):
            checking_table_updates.clear()
            for table in cut_value:
                cursor.execute("select max(insert_dttm) from bookings.update_status where table_name = %s "
                               "and insert_dttm > %s", (table, cut_value[table]))
                result = str(cursor.fetchone()[0])
                if result != 'None':
                    self.table_statuses[table] = result
            if not self.compare_lists(self.config_file['table_names'], self.table_statuses.keys()):
                time.sleep(self.config_file['update_time'])
        cursor.close()
        print(self.table_statuses)
        return self.table_statuses

    def create_result_table(self):
        cursor = self.connection.cursor()
        with open(self.config_file['path_to_sql_file']) as sql_file:
            cursor.execute(sql_file.read())
            self.connection.commit()
        cursor.close()

    def update_cutparam(self):
        cursor = self.connection.cursor()
        for table in self.table_statuses:
            cursor.execute("update target_bookings.last_taken_data set dataflow_dttm = now(), cut_value = %s "
                           "where job_name = %s and table_name = %s", (self.table_statuses[table],
                                                                       self.config_file['job_name'], table))
        self.connection.commit()
        cursor.close()

    def load_table(self):
        if self.compare_lists(self.config_file['table_names'], self.table_statuses.keys()) \
                or self.config_file['load_or_drop'] == True:
            self.create_result_table()
            self.update_cutparam()
        else:
            raise TimeoutError('Timeout expired')


if __name__ == "__main__":

    time_start = time.time()

    load_job = Sensor(sys.argv, db_name="demo", db_user="annaum", db_password="123", db_host="192.168.1.67",
                      db_port="5432")

    Sensor.table_statuses = load_job.check_table_status()

    load_job.load_table()

    load_job.connection.close()
