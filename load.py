import transform as t
import boto3
import datetime
import psycopg2
import os
import logging

# Variables
db_table = os.environ.get('us_covid_data')

# Initialize boto3 clients
ssm = boto3.client('ssm')
sns = boto3.client('sns')

# Get DB username, password, host and name for database from Parameter store
db_user = ssm.get_parameter(Name='/database/covid19/user')
db_password = ssm.get_parameter(Name='/database/covid19/password', WithDecryption=True)
db_host = ssm.get_parameter(Name='/database/covid19/endpoint')
db_name = ssm.get_parameter(Name='/database/covid19/name')

# Logging https://dev.to/aws-builders/why-you-should-never-ever-print-in-a-lambda-function-3i37
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)  # To see output in local console
logger.setLevel(logging.INFO)  # To see output in Lambda


def notification(text):
    try:
        sns.publish(TopicArn=os.environ['sns_topic'],
                    Subject='Covid19 ETL summary',
                    Message=text)
    except Exception as e:
        logger.error("Sending notification failed: {}".format(e))
        exit(1)
    logger.info(text)


def main(event, context):
        df_final = t.transform(os.environ['ny_url'], os.environ['jh_url'])
        logger.info(f"Last 5 lines of merged dataset:\n {df_final.tail(5)}\n")
        
        # CONNECTING TO THE DATABASE
        
        conn = psycopg2.connect(database=db_name['Parameter']['Value'], user=db_user['Parameter']['Value'],
                                password=db_password['Parameter']['Value'], host=db_host['Parameter']['Value'],
                                port=5432)
        cur = conn.cursor()
    
        try:
            # Create table if table doesn't exist
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {db_table} (reportdate date PRIMARY KEY, cases integer, deaths integer, recovered integer)")
            cur.execute(f"SELECT COUNT(*) AS num_rows FROM {db_table}")
            query_results = cur.fetchone()
            logger.info(f"Num of rows in db table {db_table}: {query_results[0]}")
        except (Exception, psycopg2.DatabaseError) as e:
            notification(f"Unable to find info about db table: {e}")
            exit(1)
        if query_results[0] == 0:
            # If db table is empty, insert data for the first time
            try:
                # Here we are going save the dataframe on disk as a csv file, load the csv file and use copy_from() to copy it to db table
                tmp_csv = "/tmp/db_table.csv"
                df_final.to_csv(tmp_csv, index=False, header=False)
                f = open(tmp_csv, 'r')
                cur.copy_from(f, db_table, sep=",")
                os.remove(tmp_csv)
            except (Exception, psycopg2.DatabaseError) as e:
                notification(f"First data insertion into db table failed: {e}")
                exit(1)

            # Send email notification about data insertion
            cur.execute(f"SELECT COUNT(*) AS num_rows FROM {db_table}")
            query_results = cur.fetchone()
            text = f"First data insertion successfully completed!\n"
            text += f"\nNum of rows inserted into db table {db_table}: {query_results[0]}"
            notification(text)

        else:
            # If db table is not empty, load new data records into db table
            # DELETE FROM covid19_stats WHERE reportdate=(SELECT MAX(reportdate) FROM covid19_stats)
            cur.execute(f"SELECT MAX(reportdate) FROM {db_table}")
            query_results = cur.fetchone()
            logger.info(f"Last reported date in db table is: {query_results[0]}")
            diff = max(df_final['date']).date() - query_results[0]
            logger.info(f"Num of rows different between merged dataset and db table: {diff.days}")
            if diff.days > 0:
                try:
                    logger.info("Uploading new data records into db table..")
                    # Clone table structure of destination table to a temp table
                    tmp_table = "tmp"
                    cur.execute(f"create temporary table {tmp_table} as (SELECT * FROM {db_table} limit 0)")

                    # Copy df_final data into the temp table
                    tmp_csv = "/tmp/tmp_table.csv"
                    df_final.to_csv(tmp_csv, index=False, header=False)
                    f = open(tmp_csv, 'r')
                    cur.copy_from(f, tmp_table, sep=",")
                    os.remove(tmp_csv)

                    # Copy new records present in temp table to db table based on missing reportdate rows
                    cur.execute(
                        f"INSERT INTO {db_table} (SELECT tmp.* FROM {tmp_table} LEFT JOIN {db_table} USING (reportdate) WHERE {db_table}.reportdate IS NULL)")
                    # Drop the temporary table
                    cur.execute(f"DROP TABLE {tmp_table}")
                except (Exception, psycopg2.DatabaseError) as e:
                    notification(f"Daily insertion of data failed: {e}")
                    exit(1)


                cur.close()
                conn.commit()