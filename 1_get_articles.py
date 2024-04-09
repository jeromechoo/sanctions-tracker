import sys

if len(sys.argv) < 2:
  print("Error: Data folder is required as an argument")
  sys.exit(1)

folder = sys.argv[1]
if folder[-1] != "/":
  folder = folder + "/" 

import urllib
import urllib.parse
import subprocess
import json

try:
  with open('settings.json', 'r') as settings:
    data = json.load(settings)
    TOKEN = data.get('token', '')
    if TOKEN == '<ENTER DIFFBOT TOKEN>' or not TOKEN:
      print("Error: Don't forget to enter a Diffbot API token!")
      sys.exit(1)
except IOError:
  print("Error: settings.json file not found. See README for instructions.")
  sys.exit(1)


def createQueryUrl(dqlQuery, size=50):
    url = "https://kg.diffbot.com" + \
          "/kg/v3/dql?token="+TOKEN+"&type=query&format=jsonl&size=" + str(size) + \
          "&query=" + urllib.parse.quote_plus(dqlQuery)
    print(url)
    return url

# Limit query to the first 7 days of active sanctions
query = 'type:Article or(tags.label:or("economic sanctions", "sanctions"), title:or("sanction", "sanctions", "sanctioned", "sanctioning", "pulled out", "pulling out", "pulls out", "suspended", "suspending", "suspends", "stopped", "stopping", "halted", "halting", "restricted", "restricting", "closes", "close", "shuts down")) text:or("Russia", "Ukraine") date>"2022-02-23" date<"2022-02-30" sortBy:date'

# Download all articles that match the query
p = subprocess.run(['wget', '-O', folder + "articles.jsonl", createQueryUrl(query, -1)])

if p.returncode != 0:
    print("Something went wrong")
