import re
import json
import sys
import math
import json
import urllib.request
import requests
import os.path
import fasttext

if len(sys.argv) < 2:
  print("Data folder is required as an argument")
  sys.exit(1)


folder = sys.argv[1]
if folder[-1] != "/":
  folder = folder + "/" 

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

cache = {}

if not os.path.isfile(folder+"cache.tsv"):
  tmp = open(folder+"cache.tsv", "w")
  tmp.close()
  
cache_file = open(folder+"cache.tsv", "r+")

for line in cache_file:
  fields = line.split("\t")
  if len(fields) != 2:
    continue
  (url, ret) = fields
  cache[url] = ret

def cache_result(url, ret):
  cache[url] = ret
  cache_file.write(url + "\t" + ret +"\n")
  cache_file.flush()

def queryKG(dqlQuery, size=50, from_index=0, jsonmode='simple', debug=False):
    url = "https://kg.diffbot.com" + \
          "/kg/dql_endpoint/stream?token="+TOKEN+"&type=query&size=" + str(size) + \
          "&query=" + urllib.parse.quote_plus(dqlQuery) + \
          "&jsonmode=" + jsonmode + "&from=" + str(from_index)
    if url in cache:
      return cache[url]
    print(url)
    request = urllib.request.Request(url)
    ret = urllib.request.urlopen(request, timeout=120).read().decode('utf-8')
    cache_result(url, ret)
    return ret

query = 'type:Organization diffbotUri:"{}"'

def get_organization_by_uri(diffbotUri):
  res = queryKG(query.format(diffbotUri), size=1)
  if res.strip():
    j = json.loads(res)
    return j
  return None

def force_https(url):
  return url.replace("http://", "https://")

# load ground truth
ground_truth = {} #diffbotUri -> boolean (positive or negative example)

with open(folder + "ground_truth.tsv") as gt:
  for line in gt:
    line = line.strip()
    fields = line.split("\t")
    if len(fields) < 3:
      continue
    if len(fields[0]) == 0: 
      continue #missing uri
    if len(fields[2]) == 0:
      continue # missing label
    uri = fields[0]
    diffbotId = uri[uri.rfind("/")+1:]
    uri = "https://diffbot.com/entity/" + diffbotId
    ground_truth[uri] = {"name":fields[1], "label":fields[2] == "TRUE"}

# load sanctioning companies
count = 0
model = fasttext.load_model(folder+"model.bin")

all_organizations = dict() # diffbotUri -> name, count, sentences
with open(folder + "facts.jsonl", "r") as f:
  for line in f:
    count += 1
    if count % 100 == 0:
      print("Number of documents processed: " + str(count))
    #if count > 500:
    #  break
    doc = json.loads(line)
    content = doc["title"]+"\n\n"+doc["text"]
    nl = doc.get('naturalLanguage', None)

    if nl and nl != None and 'entities' in nl:
      for entity in nl['entities']:
        if "diffbotUri" not in entity:
          continue
        types = [t.get("name", "") for t in entity.get("allTypes",[])]
        if "organization" not in types or "location" in types:
          continue
        # update all_organizations
        entity["diffbotUri"] = force_https(entity["diffbotUri"])
        if entity["diffbotUri"] not in all_organizations:
          all_organizations[entity["diffbotUri"]] = {"name":entity["name"], "entity" : {}, "chosen" : False, "status" : "", "score": 0.0, "count": 0, "firstDate": "", "sentences" : [], "ignoredSentences" : [], "seenSentences" : set()}
          if entity["diffbotUri"] in ground_truth:
            all_organizations[entity["diffbotUri"]]["ground_truth"] = ground_truth[entity["diffbotUri"]]["label"]
        
        # choose sentences
        for mention in entity["mentions"]:
          if mention["text"].lower() in ['it', 'its', 'that']:
            continue # skip some pronouns to prevent coref errors to add noise
          mentionBegin = mention["beginOffset"]
          mentionEnd = mention["endOffset"]
          for sent in nl["sentences"]:
            if mentionBegin >= sent["beginOffset"] and mentionBegin < sent["endOffset"]:
              sent_text = content[sent["beginOffset"]:sent["endOffset"]]
              if "\n" in sent_text or "\t" in sent_text or len(sent_text) < 50:
                continue
              
              normalized_text = re.sub("[^a-z]","",sent_text.lower()[0:min(50, len(sent_text))])
              if normalized_text in all_organizations[entity["diffbotUri"]]["seenSentences"]:
                continue
              all_organizations[entity["diffbotUri"]]["seenSentences"].add(normalized_text)

              sentence_for_classification = content[sent["beginOffset"]:mentionBegin] + " _entity_ " + content[mentionEnd:sent["endOffset"]]
              prediction = model.predict(sentence_for_classification)

              score = prediction[1][0]
              chosen = prediction[0][0] == '__label__True' and entity["confidence"]> 0.8
              
              sent_obj = {"text" : sent_text, "document" : doc, "score" : score}
              if chosen:
                org = get_organization_by_uri(entity["diffbotUri"])
                blocked_industries = set(["Intergovernmental Organizations", "Public Administration", "Government Departments", "Ministries", "Political Parties","Educational Organizations", "Law Firms"]) # Ignoring a few generally irrelevant industries
                if not org:
                  continue
                if "industries" not in org:
                  continue
                if len(set.intersection(blocked_industries, set(org.get("industries", [])))) > 0:
                  continue
                all_organizations[entity["diffbotUri"]]["entity"] = org
                if org.get("location",{}).get("country",{}).get("name", "") == "Russia" or org.get("location",{}).get("country",{}).get("name", "") == "Belarus":
                  all_organizations[entity["diffbotUri"]]["status"] = "Receiving Sanctions"
                else:
                  all_organizations[entity["diffbotUri"]]["status"] = "Applying Sanctions"

                if not all_organizations[entity["diffbotUri"]]["firstDate"] or doc["date"]["str"][1:11] < all_organizations[entity["diffbotUri"]]["firstDate"]:
                  all_organizations[entity["diffbotUri"]]["firstDate"] = doc["date"]["str"][1:11]
                if score > all_organizations[entity["diffbotUri"]]["score"]:
                  all_organizations[entity["diffbotUri"]]["score"] = score
                if score > 0.9:
                  all_organizations[entity["diffbotUri"]]["chosen"] = True
                all_organizations[entity["diffbotUri"]]["sentences"].append(sent_obj)                
                
              if not chosen:
                all_organizations[entity["diffbotUri"]]["ignoredSentences"].append(sent_obj)
        all_organizations[entity["diffbotUri"]]["count"] += 1

# calculate precision and recall
tp = set() #diffbotUri of true positives
fp = set() #diffbotUri of false positives
fn = set() #diffbotUri of false negatives

for (diffbotUri, value) in all_organizations.items():
  if value["chosen"]:
    if ground_truth.get(diffbotUri, {}).get("label", None):
        tp.add(diffbotUri)
    if ground_truth.get(diffbotUri, {}).get("label", None) == False:
      fp.add(diffbotUri)

print("false negatives:")
for (diffbotUri, value) in ground_truth.items():
  if value["label"] == False:
    continue
  if diffbotUri not in tp:
    fn.add(diffbotUri)
    print(diffbotUri + "\t" + value["name"])
print()

# override using ground truth
for (diffbotUri, value) in all_organizations.items():
  value["chosenWithOverride"] = value["chosen"]
  if ground_truth.get(diffbotUri, {}).get("label", None) and len(value["sentences"])>0:
    value["chosenWithOverride"] = True
  if ground_truth.get(diffbotUri, {}).get("label", None) == False:
    value["chosenWithOverride"] = False

# generate list for human review
rows = []
for (diffbotUri, value) in sorted(all_organizations.items(), key=lambda item: item[1]["count"], reverse = True):
  row = {}
  row["diffbotUri"] = diffbotUri
  row["name"] = value.get("entity", {}).get("name", value["name"]) 
  row["chosen"] = value["chosen"]
  row["chosenWithOverride"] = value["chosenWithOverride"]
  row["firstDate"] = value["firstDate"]
  row["status"] = value["status"]
  row["article_count"] = value["count"]
  row["ground_truth"] = value.get("ground_truth", None)
  row["score"] = value.get("score", 0.0)
  sentences = all_organizations[diffbotUri]["sentences"]
  sentences = sorted(sentences, key=lambda item: item["score"], reverse = True)
  ignored = all_organizations[diffbotUri]["ignoredSentences"]
  row["chosen_sentence_count"] = len(sentences)
  if len(sentences)>5:
    sentences = list(sentences)[0:5]
  if len(ignored)>5:
    ignored = list(ignored)[0:5]
  row["chosen_sentences"] = " ----- ".join([s['text'] for s in sentences])
  row["ignored_sentences"] = " ----- ".join([s['text'] for s in ignored])
  rows.append(row)

rows = sorted(rows, key=lambda item: item["chosen_sentence_count"], reverse = True)

import csv
tsv = open(folder + 'human_review.tsv', 'w')
columns = ['diffbotUri', 'name', 'ground_truth', "chosen", "chosenWithOverride", "score", 'firstDate', 'status', 'article_count', 'chosen_sentence_count', 'chosen_sentences', 'ignored_sentences']
writer = csv.DictWriter(tsv, fieldnames=columns, delimiter='\t')
writer.writeheader()

for row in rows:
  writer.writerow(row)
tsv.close()

# Sneak peak into articles
import pandas as pd
df = pd.read_csv(folder + "human_review.tsv", sep='\t')
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
print(df.head())

print("tp: " + str(len(tp)))
print("fp: " + str(len(fp)))
print("fn: " + str(len(fn)))

print("precision: {:3}".format(len(tp) / ( len(tp) + len(fp))))
print("recall: {:3}".format(len(tp) / ( len(tp) + len(fn))))

# generate csv data
rows = []
for (diffbotUri, value) in sorted(all_organizations.items(), key=lambda item: item[1]["count"], reverse = True):
  if not value["chosenWithOverride"]:
    continue
  sentences = all_organizations[diffbotUri]["sentences"]
  popularity = len(sentences)
  if len(sentences)>5:
    sentences = list(sentences)[0:5]

  for s in sentences:
    ground_truth = value.get("ground_truth", None)
    if ground_truth == False:
      continue

    row = {}
    row["diffbotUri"] = diffbotUri
    row["name"] = value["entity"]["name"]
    row["firstDate"] = value["firstDate"]
    row["country"] = value["entity"].get("location", {}).get("country", {}).get("name", "")
    row["status"] = value["status"]
    row["industries"] = ",".join(value["entity"]["industries"])
    row["logo"] = value["entity"].get("logo", "")
    row["popularity"] = popularity
    
    row["text"] = s["text"]
    row["score"] = s["score"]
    row["title"] = s["document"]["title"]
    row["date"] = s["document"]["date"]["str"][1:11]
    row["pageUrl"] = s["document"]["pageUrl"]
    row["siteName"] = s["document"]["siteName"]
    rows.append(row)

rows = sorted(rows, key=lambda item: item["popularity"], reverse = True)

tsv = open(folder + 'output.tsv', 'w')
columns = ['diffbotUri', 'name', 'firstDate', 'country', 'status', 'industries', 'logo', 'popularity', 'text', 'score', 'title', 'date', 'pageUrl', 'siteName']
writer = csv.DictWriter(tsv, fieldnames=columns, delimiter='\t')
writer.writeheader()

for row in rows:
  writer.writerow(row)
tsv.close()

# generate json data
json_out = []

for (diffbotUri, value) in sorted(all_organizations.items(), key=lambda item: item[1]["count"], reverse = True):
  if not value["chosenWithOverride"]:
    continue
  sentences = all_organizations[diffbotUri]["sentences"]
  popularity = len(sentences)
  if len(sentences)>5:
    sentences = list(sentences)[0:5]
  if len(sentences) == 0:
    continue

  org = {}
  org['id'] = value["entity"]["id"]
  org["name"] = value["entity"]["name"]
  org["firstDate"] = value["firstDate"]
  org["country"] = value["entity"].get("location", {}).get("country", {}).get("name", "")
  org["status"] = value["status"]
  org["industries"] = value["entity"]["industries"]
  org["logo"] = value["entity"].get("logo", "")
  org["summary"] = value["entity"].get("summary","")
  org["popularity"] = popularity
  
  articles = {} # article url -> {article info + references/sentences}
  for s in sentences:
    article = {}
    url = s["document"]["pageUrl"]
    if url not in articles:
      articles[url] = {"siteName":s["document"]["siteName"], "title": s["document"]["title"], "pageUrl": s["document"]["pageUrl"], "date": s["document"]["date"]["str"][1:11], "references" : []}
    articles[url]["references"].append(s["text"])
  
  org["articles"] = list(articles.values())
  json_out.append(org)

json_out = sorted(json_out, key=lambda item: item["popularity"], reverse = True)

with open(folder + "output.json", "w") as out:
  out.write(json.dumps(json_out, indent=4) + "\n")

print("number of organizations: " + str(len(json_out)))