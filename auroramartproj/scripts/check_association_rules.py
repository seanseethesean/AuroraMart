#!/usr/bin/env python3
import json
import traceback
from itertools import combinations
import os
import sys

import pandas as pd

# Ensure project root is on sys.path so local packages (adminpanel, storefront) import correctly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adminpanel.ml_utils import (
    recommend_products_from_rules,
    load_models,
    PRODUCTS_CSV_PATH,
)

out = {}
try:
    models = load_models()
    out['models_loaded'] = {k: (v is not None) for k, v in models.items()}
    ar_model = models.get('association_rules')
    # model introspection
    if ar_model is None:
        out['ar_model'] = None
    else:
        out['ar_model'] = {
            'type': str(type(ar_model)),
            'has_recommend': hasattr(ar_model, 'recommend'),
            'has_predict': hasattr(ar_model, 'predict'),
        }
        try:
            import pandas as _pd
            if isinstance(ar_model, _pd.DataFrame):
                # serialize a small sample of rules (antecedents/consequents may be sets/frozensets)
                def _serialize_rule_row(row):
                    def to_list(v):
                        if v is None:
                            return []
                        if isinstance(v, (list, tuple, set, frozenset)):
                            return [str(x) for x in v]
                        return [str(v)]

                    return {
                        'antecedents': to_list(row.get('antecedents')),
                        'consequents': to_list(row.get('consequents')),
                        'support': float(row.get('support') or 0),
                        'confidence': float(row.get('confidence') or 0),
                        'lift': float(row.get('lift') or 0),
                    }

                out['ar_model']['rules_sample'] = [
                    _serialize_rule_row(r) for r in ar_model.head(20).to_dict(orient='records')
                ]
        except Exception:
            pass

    df = pd.read_csv(PRODUCTS_CSV_PATH)
    sku_col = next((c for c in df.columns if 'sku' in c.lower()), None)
    if sku_col is None:
        sku_col = next((c for c in df.columns if 'product' in c.lower()), None)
    skus = df[sku_col].dropna().astype(str).unique().tolist() if sku_col is not None else []
    out['found_sku_column'] = sku_col
    out['num_skus'] = len(skus)

    sample = skus[:10]
    out['sample_skus'] = sample

    rec_results = []
    # test single item recommendations
    for sku in sample[:6]:
        recs = recommend_products_from_rules([sku], top_n=5)
        rec_results.append({'input': [sku], 'recs': recs})

    # test pair combinations
    pairs = list(combinations(sample, 2))[:30]
    for a, b in pairs:
        recs = recommend_products_from_rules([a, b], top_n=5)
        rec_results.append({'input': [a, b], 'recs': recs})

    out['results'] = rec_results
    # if we've found no recommendations in rec_results, also try calling the raw model if it's a DataFrame
    try:
        if ar_model is not None and 'rules_sample' in out.get('ar_model', {}) and not any(r['recs'] for r in rec_results):
            out['note'] = 'No recommendations matched sample pairs; rules sample included in ar_model.rules_sample'
    except Exception:
        pass
except Exception as e:
    out['error'] = str(e)
    out['traceback'] = traceback.format_exc()

print(json.dumps(out, indent=2, ensure_ascii=False))
