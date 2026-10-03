"""Train-fold-only preprocessing and fixed L2 logistic baselines."""
import warnings
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .features import NUMERIC_FEATURES, CATEGORICAL_FEATURES

B2A_CATEGORICAL_FEATURES = ['event_type']
B2B_CATEGORICAL_FEATURES = ['event_type', 'event_subtype_grouped']
B2B_MIN_SUBTYPE_COUNT = 3
B2B_RARE_LABEL = 'OTHER_RARE'


def feature_columns(level):
    if level not in ('B1', 'B2a', 'B2b', 'B2'):
        raise ValueError(level)

    if level == 'B1':
        categorical = []
    elif level == 'B2a':
        categorical = B2A_CATEGORICAL_FEATURES
    elif level == 'B2b':
        categorical = B2B_CATEGORICAL_FEATURES
    else:
        categorical = CATEGORICAL_FEATURES

    return NUMERIC_FEATURES + categorical


def build_b2b_subtype_keep_set(train):
    counts = train['event_subtype'].value_counts(dropna=True)
    return set(counts[counts >= B2B_MIN_SUBTYPE_COUNT].index.astype(str))


def add_b2b_grouped_subtype(data, keep_set):
    out = data.copy()

    def group_value(v):
        if pd.isna(v) or not str(v).strip():
            return B2B_RARE_LABEL
        value = str(v)
        return value if value in keep_set else B2B_RARE_LABEL

    out['event_subtype_grouped'] = out['event_subtype'].map(group_value)
    return out


def feature_frame(data, level):
    x = data.loc[:, feature_columns(level)].copy()

    for c in NUMERIC_FEATURES:
        x[c] = pd.to_numeric(x[c], errors='coerce').replace([np.inf, -np.inf], np.nan)

    if level == 'B1':
        categorical = []
    elif level == 'B2a':
        categorical = B2A_CATEGORICAL_FEATURES
    elif level == 'B2b':
        categorical = B2B_CATEGORICAL_FEATURES
    else:
        categorical = CATEGORICAL_FEATURES

    for c in categorical:
        x[c] = x[c].map(
            lambda v: str(v) if pd.notna(v) and str(v).strip() else np.nan
        )

    return x


def make_model(level):
    numeric = Pipeline([
        ('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
        ('scale', StandardScaler()),
    ])

    transformers = [('numeric', numeric, NUMERIC_FEATURES)]

    if level == 'B1':
        categorical_columns = []
    elif level == 'B2a':
        categorical_columns = B2A_CATEGORICAL_FEATURES
    elif level == 'B2b':
        categorical_columns = B2B_CATEGORICAL_FEATURES
    else:
        categorical_columns = CATEGORICAL_FEATURES

    if categorical_columns:
        categorical = Pipeline([
            ('impute', SimpleImputer(strategy='constant', fill_value='Unknown')),
            ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
        ])
        transformers.append(('categorical', categorical, categorical_columns))

    return Pipeline([
        ('features', ColumnTransformer(transformers)),
        ('logistic', LogisticRegression(
            penalty='l2',
            C=1.0,
            solver='liblinear',
            max_iter=3000,
            random_state=0,
        )),
    ])


def fit_model(train, labels, level):
    if len(train) == 0 or len(np.unique(labels)) < 2:
        return None

    model = make_model(level)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore',
            message='.*penalty.*deprecated.*',
            category=FutureWarning,
        )
        model.fit(feature_frame(train, level), labels)

    return model


def predict(model, data, level, base_rate):
    if model is None:
        return np.full(len(data), base_rate, dtype=float)

    return model.predict_proba(feature_frame(data, level))[:, 1]


def coefficients(dataset, label='target', level='B2'):
    model = fit_model(dataset, dataset[label], level)

    if model is None:
        return pd.DataFrame(
            columns=['feature', 'coefficient', 'abs_coefficient']
        )

    names = model['features'].get_feature_names_out()
    coef = model['logistic'].coef_[0]

    return pd.DataFrame({
        'feature': names,
        'coefficient': coef,
        'abs_coefficient': np.abs(coef),
    }).sort_values('abs_coefficient', ascending=False)
