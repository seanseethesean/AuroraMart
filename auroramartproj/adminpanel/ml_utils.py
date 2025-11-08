import os
import joblib
from functools import lru_cache
from django.apps import apps
import logging
import pandas as pd
from typing import List, Any, Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_models() -> dict:
    """Load and cache joblib models from adminpanel/mlmodels.

    Returns a dict with keys 'decision_tree' and 'association_rules'. Values may be None if file missing.
    """
    loaded = {'decision_tree': None, 'association_rules': None}
    try:
        app_path = apps.get_app_config('adminpanel').path
        models_dir = os.path.join(app_path, 'mlmodels')

        # Tolerant loader: scan for any .joblib files and map by filename keywords.
        if os.path.isdir(models_dir):
            for fname in os.listdir(models_dir):
                if not fname.lower().endswith('.joblib'):
                    continue
                fpath = os.path.join(models_dir, fname)
                lname = fname.lower()
                try:
                    if any(k in lname for k in ('customer', 'b2c', 'decision', 'tree')) and loaded['decision_tree'] is None:
                        loaded['decision_tree'] = joblib.load(fpath)
                        logger.info('Loaded decision tree model from %s', fpath)
                        continue
                    if any(k in lname for k in ('product', 'trans', 'transaction', 'association', 'assoc')) and loaded['association_rules'] is None:
                        loaded['association_rules'] = joblib.load(fpath)
                        logger.info('Loaded association rules model from %s', fpath)
                        continue
                    # fallback: if only one model present, map first to decision_tree
                    if loaded['decision_tree'] is None and loaded['association_rules'] is None:
                        loaded['decision_tree'] = joblib.load(fpath)
                        logger.info('Loaded model (fallback) from %s', fpath)
                except Exception:
                    logger.exception('Failed loading model file %s', fpath)
        else:
            logger.info('Models directory does not exist: %s', models_dir)
    except Exception:
        logger.exception('Error while locating adminpanel app path for mlmodels')

    return loaded


def customer_to_feature_df(customer, expected_columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Convert a Customer model instance to a DataFrame matching the DT training features.

    IMPORTANT: replace the implementation below with the exact preprocessing used in the
    training notebook (one-hot encoding, column order, scaling, etc.). This placeholder
    returns a minimal DataFrame and will likely not work with your trained model until
    you adapt it.
    """
    # pandas is imported at module level as pd

    if customer is None:
        return pd.DataFrame()

    # Base raw features we can safely extract from typical Customer models.
    # Add or adjust these keys to match the attributes on your Customer model.
    feat = {
        'age': getattr(customer, 'age', 0) or 0,
        'household_size': getattr(customer, 'household_size', 1) or 1,
        'has_children': 1 if getattr(customer, 'has_children', False) else 0,
        'gender': (getattr(customer, 'gender', '') or '').strip(),
        'monthly_income': getattr(customer, 'monthly_income', 0) or 0,
        'education': (getattr(customer, 'education', '') or '').strip(),
        'occupation': (getattr(customer, 'occupation', '') or '').strip(),
        'marital_status': (getattr(customer, 'marital_status', '') or '').strip(),
    }

    base_df = pd.DataFrame([feat])

    # If we don't have expected_columns, return the raw DataFrame
    if not expected_columns:
        return base_df

    # Build a DataFrame that matches expected_columns (order and names).
    out = pd.DataFrame(columns=expected_columns)

    for col in expected_columns:
        if col in base_df.columns:
            out.loc[0, col] = base_df.loc[0, col]
            continue

        # Heuristic: treat columns like '<field>_<value>' as one-hot encodings
        if '_' in col:
            field, _, val = col.partition('_')
            if field in base_df.columns and isinstance(base_df.loc[0, field], str):
                out.loc[0, col] = 1 if base_df.loc[0, field] == val else 0
                continue

        # If column looks numeric, default to 0, otherwise empty/zero
        out.loc[0, col] = 0

    # Ensure types (fill NaNs with zeros)
    out = out.fillna(0)
    # Reindex to ensure exact column order
    out = out.reindex(columns=expected_columns)
    return out


def predict_preferred_category_for_customer(customer) -> Optional[Any]:
    """Return the predicted preferred category for the given Customer or None.

    Uses the cached decision-tree model if available. Returns None on error or if model missing.
    """
    models = load_models()
    dt = models.get('decision_tree')
    if dt is None:
        return None

    try:
        # If the model stores feature names (sklearn >=0.23), use them to build matching input
        expected = None
        if hasattr(dt, 'feature_names_in_'):
            try:
                expected = list(dt.feature_names_in_)
            except Exception:
                expected = None

        df = customer_to_feature_df(customer, expected_columns=expected)
        if df.empty:
            return None
        # Ensure our df has same columns ordering as model expects (sklearn checks names)
        if expected:
            df = df.reindex(columns=expected, fill_value=0)

        pred = dt.predict(df)
        return pred[0] if hasattr(pred, '__len__') else pred
    except Exception:
        logger.exception('Decision tree prediction failed')
        return None


def recommend_products_from_rules(basket_items: List[Any], top_n: int = 10) -> List[Any]:
    """Return recommended product identifiers using the association-rules model.

    The association model's API varies; this wrapper tries common patterns and returns
    a list of SKUs/IDs (may be empty).
    """
    models = load_models()
    ar = models.get('association_rules')
    if ar is None:
        return []

    try:
        # try a recommend method
        if hasattr(ar, 'recommend'):
            try:
                return ar.recommend(basket_items, top_n=top_n)
            except TypeError:
                return ar.recommend(basket_items)

        # try predict
        if hasattr(ar, 'predict'):
            return list(ar.predict([basket_items]))

        # if it's a DataFrame-like object, attempt simple rule lookup
        try:
            if isinstance(ar, pd.DataFrame):
                recs = []
                for item in basket_items:
                    matched = ar[ar['antecedents'].apply(lambda a: item in a if hasattr(a, '__iter__') else False)]
                    for conseq in matched['consequents']:
                        for c in (conseq if hasattr(conseq, '__iter__') else [conseq]):
                            if c not in recs:
                                recs.append(c)
                            if len(recs) >= top_n:
                                return recs
                return recs
        except Exception:
            pass

    except Exception:
        logger.exception('Association rules recommendation failed')

    return []
