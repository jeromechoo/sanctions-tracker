As of March 21st 2022, we've tracked at least 602 companies from 50 countries who've announced sanctions in response to Russia's invasion of Ukraine. The complete dataset is available for download free at [diffbot.com](https://diffbot.com/insights/every-company-affected-by-sanctions/). 

We've since paused real-time tracking as daily new sanctions have fallen tremendously, but you can rebuild it for yourself or extend the app to track any kind of market monitoring signal you like.

Feel free to start here or [follow the step by step tutorial](https://diffbot.com/insights/build-a-sanctions-tracker).

## Requirements
* Python 3.8+
* Diffbot API token (get a [trial token here](https://app.diffbot.com/get-started))

## Get Started
1. Clone the repository with `git clone`
2. Navigate into the root directory with `cd Sanctions`
3. Install fasttext and pandas with
	```bash
	python3 -m pip install fasttext pandas
	```
4. Create a `settings.json` file with the following data

	```json
	{
		"token": "YOUR DIFFBOT TOKEN"
	}
	```

5. Follow the steps below to run each script

## [Step 1 — Get Articles](https://www.diffbot.com/insights/build-a-sanctions-tracker/#step-1--get-news)
Download all the [articles from the Diffbot Knowledge Graph](https://www.diffbot.com/data/article/) that match a [DQL](https://docs.diffbot.com/docs/en/dql-index) query targeting "high likelihood of sanctions" articles into a file called `articles.jsonl`. Depending on the date range, this can be several thousands of articles and take some time.
> 💡 Skip this step if you're on a trial token or you will blow through your trial limits. A copy of `articles.jsonl` covering the first 7 days after the day of Russia's invasion is provided in `sanctions/`. 
```bash
python3 1_get_articles.py sanctions/
```

## [Step 2 — Identify Organizations](https://www.diffbot.com/insights/build-a-sanctions-tracker/#step-2--identify-organizations)
Process every article in `sanctions/articles.jsonl` through [NLP API](https://www.diffbot.com/products/natural-language/), generating a list of sentences mentioning organizations that we can later classify. The resulting data is saved as `facts.jsonl`.
> 💡 Skip this step if on a trial token. A copy of `facts.jsonl` is also included in `sanctions/`.
```bash
python3 2_call_nl.py sanctions/
```

## [Step 3 — Prepare Training](https://www.diffbot.com/insights/build-a-sanctions-tracker/#step-3--train-a-classifier-to-identify-sanctions)
Samples training and validation datasets from cross-referencing `facts.jsonl` with known sanctions in `ground_truth.tsv` for training and evaluating our machine learning classifier.
```bash
python3 3_prepare_training.py sanctions/
```

## [Step 4 — Train Model](https://www.diffbot.com/insights/build-a-sanctions-tracker/#step-4--use-the-classifier-to-predict-sanctions)
Trains the classifier model using the training and validation datasets. Outputs a precision and recall we can use to gauge effectiveness of the classifier.
```bash
python3 4_train_model.py sanctions/
```

## Step 5 - Generate Data
Runs the classifier model across the rest of the articles to generate a dataset of sanctions. Also enhances each organization with firmographics from the Diffbot Knowledge Graph for better context.
```bash
python3 5_generate.py sanctions/
```
