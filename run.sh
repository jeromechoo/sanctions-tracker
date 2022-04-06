#/bin/bash
python3 --version
python3 -m pip install fasttext pandas
python3 1_get_articles.py sanctions/
python3 2_call_nl.py sanctions/
python3 3_prepare_training.py sanctions/
python3 4_train_model.py sanctions/
python3 5_generate.py sanctions/