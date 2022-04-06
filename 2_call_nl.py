import sys
import json
import requests
from multiprocessing import Pool

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


def callNaturalLanguage(payload, fields):
    # Progress Meter
    print(".", end="", flush=True)
    
    ret = None
    try:
      res = None
      res = requests.post("https://nl.diffbot.com/v1/?fields={}&token={}".format(fields, TOKEN), json=payload, timeout=120)
      ret = res.json()
    except requests.Timeout as err:
      print("\nRequest timeout for payload:\n" + json.dumps(payload) + "\n")
    except:
      print("\nError for payload: " + json.dumps(payload) + "\n")
      if res:
        print("\nBad response: " + res.text + "\n")
    return ret

def processArticle(article):
  title = article.get('title', '')
  text = article.get('text', '')
  article['naturalLanguage'] = callNaturalLanguage({
      "content": title+"\n\n"+text,
      "format" : "plain text with title",
      "lang": "en",
    }, "entities, facts, sentences")
  return article

if __name__ ==  '__main__':
    articles = []
    with open(folder + "articles.jsonl", "r") as f:
        for line in f:
            article = json.loads(line)
            # truncate articles that are too long
            if 'text' in article and len(article['text']) > 10000:
              article['text'] = article['text'][0:10000]
            articles.append(article)

    # run many requests to the Natural Language API in parallel to speed things up
    with Pool(50) as p:
        res = p.map(processArticle, articles)

    with open(folder + "facts.jsonl", "w") as nl:
        for article in res:
          nl.write(json.dumps(article) + "\n")
            
                


