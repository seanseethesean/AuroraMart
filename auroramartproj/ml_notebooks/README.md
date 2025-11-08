Notebooks for model training and inference

Place the instructor-provided notebooks here for reference and to copy preprocessing steps into your Django helpers.

- decision_tree_classifier.ipynb — contains the pipeline and feature engineering used to train the customer decision-tree.
- association_rules_mining.ipynb — contains the association rules mining code and any helper functions used to generate recommendations.

How to use:
1. Open a notebook, find the preprocessing cells (encoding, one-hot, scaling, column order).
2. Copy those steps into a helper function inside `adminpanel/` (for example `adminpanel/ml_utils.py`) so the web app can apply identical preprocessing before calling `model.predict()`.
