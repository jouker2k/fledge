#!/bin/bash

echo "--- installing virtualenv ---"
# shall ignore if already installed
pip install virtualenv

# which python3
python3_path=$( which python3 )

echo "--- setting the virtualenv using python3 path ---"
virtualenv --python=$python3_path venv/fogenv
source venv/fogenv/bin/activate

# make sure you see prompt now with (venv/fogenv) as prefix


# whenever you add new dependency
# better you add to requirements.txt and run pip install -r requirements.txt
# or install using `pip install <dependency-name>` and do `pip freeze > requirements.txt ` for future / other's usage

echo "--- installing requirements which were frozen using [pip freeze > requirements.txt]---"
pip install -r requirements.txt


# run tests?

# echo "--- deactivating the virtualenv ---"
# deactivate

# echo "--- removing virtualenv directory ---"
# rm -rf venv/fogenv/