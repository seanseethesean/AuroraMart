from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List, Optional

from collections.abc import Iterable as IterableABC

import joblib
import pandas as pd

logger = logging.getLogger(__name__)


APP_DIR = Path(__file__).resolve().parent
MODEL_DIR_CANDIDATES = [APP_DIR / "models", APP_DIR / "mlmodels"]
DATASETS_DIR = APP_DIR / "datasets"
PRODUCTS_CSV_PATH = DATASETS_DIR / "products_500.csv"


def _normalize_token(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _key(value: Any) -> Optional[str]:
    token = _normalize_token(value)
    return token.upper() if token else None


def _build_identifier_maps() -> tuple[dict[str, str], dict[str, str]]:
    id_to_sku: dict[str, str] = {}
    sku_to_id: dict[str, str] = {}

    if not PRODUCTS_CSV_PATH.exists():
        logger.warning("Products dataset not found at %s", PRODUCTS_CSV_PATH)
        return id_to_sku, sku_to_id

    try:
        df = pd.read_csv(PRODUCTS_CSV_PATH)
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(PRODUCTS_CSV_PATH, encoding='latin-1')
        except Exception:
            logger.exception("Failed reading product catalogue from %s", PRODUCTS_CSV_PATH)
            return id_to_sku, sku_to_id
    except Exception:
        logger.exception("Failed reading product catalogue from %s", PRODUCTS_CSV_PATH)
        return id_to_sku, sku_to_id

    column_map = {col.strip(): col for col in df.columns}
    sku_col = next(
        (column_map[name] for name in (
            "sku",
            "SKU",
            "sku code",
            "SKU code",
            "Sku",
            "Sku code",
            "Product SKU",
            "Product sku",
            "Product code",
            "product_code",
        ) if name in column_map),
        None,
    )

    if not sku_col:
        logger.warning("Could not locate a SKU column in %s", PRODUCTS_CSV_PATH)
        return id_to_sku, sku_to_id

    id_col = next(
        (column_map[name] for name in (
            "model_id",
            "Model ID",
            "product_id",
            "Product ID",
            "id",
            "ID",
            "sku code",
            "SKU code",
        ) if name in column_map),
        sku_col,
    )

    if id_col == sku_col:
        series = df[sku_col].dropna()
        for value in series:
            model_key = _key(value)
            sku_value = _normalize_token(value)
            if not model_key or not sku_value:
                continue
            id_to_sku.setdefault(model_key, sku_value)
            sku_key = _key(sku_value)
            if sku_key:
                sku_to_id.setdefault(sku_key, model_key)
                sku_to_id.setdefault(sku_value, model_key)
    else:
        subset = df[[id_col, sku_col]].dropna()
        for model_value, sku_value in subset.itertuples(index=False, name=None):
            model_key = _key(model_value)
            sku_text = _normalize_token(sku_value)
            if not model_key or not sku_text:
                continue
            id_to_sku.setdefault(model_key, sku_text)
            sku_key = _key(sku_text)
            if sku_key:
                sku_to_id.setdefault(sku_key, model_key)
                sku_to_id.setdefault(sku_text, model_key)

    return id_to_sku, sku_to_id


ID_TO_SKU, SKU_TO_ID = _build_identifier_maps()


@lru_cache(maxsize=1)
def load_models() -> dict[str, Optional[Any]]:
    """Load and cache joblib models from adminpanel/models."""

    loaded: dict[str, Optional[Any]] = {'decision_tree': None, 'association_rules': None}
    models_dir = next((path for path in MODEL_DIR_CANDIDATES if path.exists()), None)

    if models_dir is None:
        logger.warning(
            "Model artefact directory missing. Tried: %s",
            ", ".join(str(path) for path in MODEL_DIR_CANDIDATES),
        )
        return loaded

    # Use the filenames provided by the course (professor):
    # - b2c_customers_100.joblib (decision tree classifier)
    # - b2c_products_500_transactions_50k.joblib (association rules dataframe)
    artefacts = {
        'decision_tree': models_dir / 'b2c_customers_100.joblib',
        'association_rules': models_dir / 'b2c_products_500_transactions_50k.joblib',
    }

    for key, path in artefacts.items():
        if not path.exists():
            logger.warning("Expected %s artefact not found: %s", key, path)
            continue
        try:
            loaded[key] = joblib.load(path)
            logger.info("Loaded %s model from %s", key, path)
        except Exception:
            logger.exception("Failed loading %s model from %s", key, path)

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


def recommend_products_from_rules(basket_items: List[Any], top_n: int = 5) -> List[str]:
    """Return SKU recommendations derived from the association-rules model."""

    if top_n <= 0:
        return []

    model_basket: List[str] = []
    seen_models: set[str] = set()
    for item in basket_items:
        key = _key(item)
        if not key:
            continue
        model_id = SKU_TO_ID.get(key)
        if not model_id or model_id in seen_models:
            continue
        seen_models.add(model_id)
        model_basket.append(model_id)

    if not model_basket:
        return []

    ar_model = load_models().get('association_rules')
    if ar_model is None:
        return []

    candidate_ids = _invoke_rules_model(ar_model, model_basket, top_n=top_n * 2)

    recommendations: List[str] = []
    seen_skus: set[str] = set()
    for candidate in candidate_ids:
        key = _key(candidate)
        if not key:
            continue
        sku = ID_TO_SKU.get(key)
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        recommendations.append(sku)
        if len(recommendations) >= top_n:
            break

    return recommendations


def _invoke_rules_model(model: Any, model_basket: List[str], top_n: int) -> List[str]:
    try:
        if hasattr(model, 'recommend'):
            try:
                result = model.recommend(model_basket, top_n=top_n)
            except TypeError:
                result = model.recommend(model_basket)
            return list(_iter_tokens(result))

        if hasattr(model, 'predict'):
            predicted = model.predict([model_basket])
            if isinstance(predicted, (list, tuple)) and predicted:
                predicted = predicted[0]
            return list(_iter_tokens(predicted))

        if isinstance(model, pd.DataFrame):
            tokens: List[str] = []
            antecedent_col = 'antecedents'
            consequent_col = 'consequents'
            if antecedent_col in model.columns and consequent_col in model.columns:
                basket_set = set(model_basket)
                for _, row in model.iterrows():
                    antecedents = row[antecedent_col]
                    if isinstance(antecedents, IterableABC) and not isinstance(antecedents, (str, bytes)):
                        antecedent_values = {str(a).strip() for a in antecedents}
                    else:
                        antecedent_values = set()
                    if antecedent_values and not antecedent_values.issubset(basket_set):
                        continue
                    tokens.extend(_iter_tokens(row[consequent_col]))
                    if len(tokens) >= top_n:
                        break
            return tokens

    except Exception:
        logger.exception('Association rules recommendation failed')

    return []


def _iter_tokens(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, pd.Series):
        return _iter_tokens(value.tolist())
    if isinstance(value, (list, tuple, set, frozenset)):
        tokens: List[str] = []
        for item in value:
            tokens.extend(list(_iter_tokens(item)))
        return tokens
    token = _normalize_token(value)
    return [token] if token else []
