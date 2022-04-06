import fasttext
import sys

if len(sys.argv) < 2:
  print("Data folder is required as an argument")
  sys.exit(1)


folder = sys.argv[1]
if folder[-1] != "/":
  folder = folder + "/" 

# train classifier
model = fasttext.train_supervised(input=folder + "training.txt", lr=0.1, epoch=25, wordNgrams=2)
model.save_model(folder + "model.bin")

# load and evaluate classifier 
model = fasttext.load_model(folder + "model.bin")

print("evaluation:")
print("number of samples, precision and recall: " + str(model.test(folder+"validation.txt")))

print("examples:")

example1 = "France’s Renault, which controls Russian car maker  _entity_ , fell 9.3 per cent."
print(str(model.predict(example1)) + " for: " + example1)

example2 = "Germany's Lufthansa halted flights to Ukraine from Monday, joining  _entity_  which already suspended flights."
print(str(model.predict(example2)) + " for: " + example2)
