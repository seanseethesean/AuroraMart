#!/usr/bin/env python3
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auroramartproj.settings')

from pathlib import Path
import joblib
import pandas as pd

MODELS_DIR = Path(PROJECT_ROOT) / 'adminpanel' / 'mlmodels'
print('Models dir:', MODELS_DIR)
if not MODELS_DIR.exists():
    print('Models directory does not exist')
    sys.exit(1)

for p in sorted(MODELS_DIR.iterdir()):
    try:
        size = p.stat().st_size
    except Exception:
        size = 'unknown'
    print(f'- {p.name} (size={size})')

# Attempt to load with adminpanel.ml_utils loader if available
try:
    from adminpanel.ml_utils import load_models, ID_TO_SKU, SKU_TO_ID
    models = load_models()
    for k, v in models.items():
        print('\nModel key:', k)
        if v is None:
            print('  Not loaded (None)')
            continue
        print('  Type:', type(v))
        try:
            if isinstance(v, pd.DataFrame):
                print('  DataFrame shape:', v.shape)
                print('  Columns:', list(v.columns[:10]))
                print('  Head:')
                print(v.head(3).to_dict(orient='records'))
            else:
                # generic object (could be sklearn estimator)
                cls = type(v)
                print('  Class repr:', cls)
                if hasattr(v, 'feature_names_in_'):
                    try:
                        print('  feature_names_in_:', list(v.feature_names_in_))
                    except Exception:
                        pass
                if hasattr(v, 'classes_'):
                    try:
                        print('  classes_:', getattr(v, 'classes_'))
                    except Exception:
                        pass
        except Exception as e:
            print('  Error introspecting model:', e)

    # show mapping sizes
    try:
        print('\nID_TO_SKU count:', len(ID_TO_SKU))
        print('SKU_TO_ID count:', len(SKU_TO_ID))
    except Exception:
        pass
except Exception as e:
    print('Could not import adminpanel.ml_utils.load_models:', e)
    # try direct joblib loads as fallback
    for p in sorted(MODELS_DIR.iterdir()):
        if p.suffix == '.joblib' or p.suffix == '.pkl':
            print('\nLoading', p.name)
            try:
                obj = joblib.load(p)
                print('  Loaded type:', type(obj))
                if isinstance(obj, pd.DataFrame):
                    print('  DataFrame shape:', obj.shape)
                else:
                    print('  repr:', repr(obj)[:200])
            except Exception as e2:
                print('  Failed to load:', e2)

print('\nDone')
