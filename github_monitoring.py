import logging
import os
import json
import requests
import sqlite3
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler  
import argparse

webhook_url = "https://oncall.site/integrations/v1/webhook/111111111111111111/"     #replace with your oncall webhook url
github_auth = "Bearer ghp_11111111111111111111111111111"                            #replace with your github token

bd_path = "/opt/monitoring/db/github_monitoring.db"                                 #path to database (make persistent if in docker)
headers_for_oncall = {"Content-Type": "Application/json"}
headers_for_github = {"Accept": "application/vnd.github+json", "Authorization": github_auth, "X-GitHub-Api-Version": "2022-11-28"}

log_file = logging.FileHandler('github_monitoring.log')
console_out = logging.StreamHandler()
logging.basicConfig(handlers=(log_file, console_out), level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

#creating a database
def creating_database():
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE releases (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tag_name TEXT, date TEXT, html_url TEXT, org TEXT, repo TEXT, sended TEXT)")
        cursor.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, date TEXT, org TEXT, repo TEXT, sended TEXT)")
        connection.close()
    except:
        logging.critical("Failed creating database")

#search in the database of releases\tags that were not sent in oncall
def search_not_sent_releases_or_tags():
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM releases WHERE (sended = 0)")
        releases = cursor.fetchall()
        cursor.execute("SELECT * FROM tags WHERE (sended = 0)")
        tags = cursor.fetchall()
        connection.close()
        return releases, tags
    except:
        logging.error("Failed searching the database for information about releases/tags that were not sent to oncall.")

#sending release information to oncall
def send_release_oncall(status, name, tag_name, date, html_url, organization, repository):
    try:
        data = {"status": status, "name": name, "tag_name": tag_name, "date": date, "html_url": html_url, "organization": organization, "repository": repository}
        response = requests.post(webhook_url, data = json.dumps(data), headers = headers_for_oncall)
        return response.status_code
    except:
        logging.error("Failed sending release info to oncall.")

#sending tag information to oncall
def send_tag_oncall(status, ref, date, organization, repository):
    try:
        data = {"status": status, "ref": ref, "date": date, "organization": organization, "repository": repository}
        response = requests.post(webhook_url, data = json.dumps(data), headers = headers_for_oncall)
        return response.status_code
    except:
        logging.error("Failed sending tag info to oncall.")

#mark the releases\tags as successfully sending
def edit_release_or_tag(id, table):
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        query = f"UPDATE {table} SET sended = 1 WHERE id = {id}"
        cursor.execute(query)
        connection.commit()
        connection.close()
    except:
        logging.error("Failed editing information in the database.")

#download release information from github
def download_release(organization, repository):
    try:
        response = requests.get(f"https://api.github.com/repos/{organization}/{repository}/releases/latest", headers = headers_for_github)
        text_response = json.loads(response.text)
        return text_response["name"], text_response["tag_name"], text_response["published_at"], text_response["html_url"]
    except:
        logging.error("Failed loading information from github.")

#download tag information from github
def download_tag(organization, repository):
    try:
        response = requests.get(f"https://api.github.com/repos/{organization}/{repository}/git/refs/tags", headers = headers_for_github)
        text_response = json.loads(response.text)
        last_tag = text_response.pop()
        return last_tag["ref"]
    except:
        logging.error("Failed loading information from github.")

#check if a release exists in the database
def check_release(name, tag_name, published_at, html_url):
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        cursor.execute("SELECT EXISTS (SELECT * FROM releases WHERE (name = ?) AND (tag_name = ?) AND (date = ?) AND (html_url = ?))", (name, tag_name, published_at[0:10], html_url))
        result = cursor.fetchone()
        connection.close()
        return result[0]
    except:
        logging.error("Failed reading release information from database.")

#check if a tag exists in the database
def check_tag(ref, organization, repository):
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        cursor.execute("SELECT EXISTS (SELECT * FROM tags WHERE (ref = ?) AND (org = ?) AND (repo = ?))", (ref, organization, repository))
        result = cursor.fetchone()
        connection.close()
        return result[0]
    except:
        logging.error("Failed reading tag information from database.")

#save release information to database
def save_release(name, tag_name, published_at, html_url, organization, repository):
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        cursor.execute("INSERT INTO releases (name, tag_name, date, html_url, org, repo, sended) VALUES (?, ?, ?, ?, ?, ?, 0)", (name, tag_name, published_at[0:10], html_url, organization, repository))
        connection.commit()
        connection.close()
    except:
        logging.error("Failed saving release information to database.")

#save tag information to database
def save_tag(ref, organization, repository):
    try:
        connection = sqlite3.connect(bd_path)
        cursor = connection.cursor()
        date = datetime.date.today()
        cursor.execute("INSERT INTO tags (ref, date, org, repo, sended) VALUES (?, ?, ?, ?, 0)", (ref, date, organization, repository))
        connection.commit()
        connection.close()
    except:
        logging.error("Failed saving tag information to database.")

#download information about tags and releases, saving information to a database, sending information to oncall
def job_for_scheduler(config):
    if not os.path.exists(bd_path):
        creating_database()
    
    for releases in config["releases"]:
        organization = releases["organization"]
        repository = releases["repository"]
        name, tag_name, published_at, html_url = download_release(organization, repository)
        id = check_release(name, tag_name, published_at, html_url)
        if not id:
            save_release(name, tag_name, published_at, html_url, organization, repository)

    for tags in config["tags"]:
        organization = tags["organization"]
        repository = tags["repository"]
        ref = download_tag(organization, repository)
        id = check_tag(ref, organization, repository)
        if not id:
            save_tag(ref, organization, repository)

    releases, tags = search_not_sent_releases_or_tags()
    for release in releases:
        print(release)
        response = send_release_oncall("firing", release[1], release[2], release[3], release[4], release[5], release[6])
        if response == 200:
            edit_release_or_tag(release[0], "releases")
            send_release_oncall("resolved", release[1], release[2], release[3], release[4], release[5], release[6])
    for tag in tags:
        response = send_tag_oncall("firing", tag[1], tag[2], tag[3], tag[4])
        if response == 200:
            edit_release_or_tag(tag[0], "tags")
            send_tag_oncall("resolved", tag[1], tag[2], tag[3], tag[4])

parser = argparse.ArgumentParser(description='help')
parser.add_argument("--config", type=argparse.FileType('r'))

try:
    args = parser.parse_args()
    config = json.load(args.config)
    scheduler = BlockingScheduler()
    scheduler.add_job(job_for_scheduler, "interval", hours=1, args=[config]) # change the interval as you like
    logging.info("Schedule job created")
    scheduler.start()
except:
    logging.critical("Failed to read config file.")


