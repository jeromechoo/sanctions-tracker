import re
import json
import sys
import random 

if len(sys.argv) < 2:
  print("Data folder is required as an argument")
  sys.exit(1)


folder = sys.argv[1]
if folder[-1] != "/":
  folder = folder + "/" 

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

# generate training data
sentences = {} # sentence -> {label, validation, diffbotUri, name}
random.seed(77777)

with open(folder + "facts.jsonl", "r") as f:
  for line in f:
    doc = json.loads(line)
    content = doc["title"]+"\n\n"+doc["text"]
    nl = doc.get('naturalLanguage', None)

    if nl and nl != None and 'entities' in nl:
      for entity in nl['entities']:        
        if "diffbotUri" not in entity:
          continue
        entity["diffbotUri"] = force_https(entity["diffbotUri"])
        if entity['diffbotUri'] not in ground_truth:
          continue
        
        label = ground_truth[entity["diffbotUri"]]["label"]
        validation = random.random()>0.8 # 80% of organizations are used for validation only

        for mention in entity["mentions"]:
          mentionBegin = mention["beginOffset"]
          mentionEnd = mention["endOffset"]
          for sent in nl["sentences"]:
            if mentionBegin >= sent["beginOffset"] and mentionBegin < sent["endOffset"]: # Ensure organization is mentioned in the sentence
              sent_text = content[sent["beginOffset"]:sent["endOffset"]]
              
              if "\n" in sent_text or "\t" in sent_text or len(sent_text) < 50:
                continue
              
              after = content[mentionEnd:min(sent["endOffset"],mentionEnd + 30)].lower()
              after = " " + after + " "
              before = content[max(0,mentionBegin - 10):mentionBegin].lower()
              before = " " + before + " "
              
              keywords = ["disconnect", "disconnects", "disconnected", "disconnecting", 
              "pause", "pauses", "paused", "pausing", 
              "block", "blocks", "blocked", "blocking", 
              "sanction", "sanctions", "sanctioned", "sanctioning", 
              "halt", "halts", "halting", "halted", 
              "suspend", "suspends", "suspended", "suspending", 
              "to stop", "stops", "stopped", "stopping", 
              "prohibit", "prohibits", "prohibited", "prohibiting", 
              "remove", "removed", "removing",
              "no-fly", "no fly", 
              "to leave", "leaving", "left", "leaves",
              "to cancel", "cancels", "cancelling", "cancelled",
              "to close", "closes", "closed", "closing",
              "shut down", "shuts down", "shutting down", "shutted down",
              "restrict", "restricts", "restricted", "restricting",
              "pulling out", "pulled out", "pulls out", "pulls out",
              "withdrew", "withdraw", "withdraws", "withdrawing",
              "cease", "ceasing", "ceased", "ceases",
              "barred", "no longer",
              "exclude", "excluded", "excluding", "excludes",
              "blacklisting", "blacklist", "blacklists", "blacklisted"]
              foundKeyword = False
              for k in keywords:
                if re.match(r".*\b"+k+r"\b.*", before + " " + after):
                  foundKeyword = True
              
              normalized_text = content[sent["beginOffset"]:mentionBegin] + " _entity_ " + content[mentionEnd:sent["endOffset"]]
              
              if (label and foundKeyword) or (label == False):
                sentences[normalized_text] = {"label":label, "validation":validation, "diffbotUri":entity["diffbotUri"], "name" : ground_truth[entity["diffbotUri"]]["name"]}

train = open(folder + "training.txt", "w")
val = open(folder + "validation.txt", "w")

for (sentence, obj) in sentences.items():
  label = "__label__"+str(obj["label"])
  line = label + " " + sentence
  if obj['validation']:
    val.write(line + "\n")
  else:
    train.write(line + "\n")

train.close()
val.close()