from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import List, Sequence

import joblib
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder


class RuleRecommender:
    """Lightweight wrapper that exposes a recommend(basket, top_n) API."""

    def __init__(self, lookup: dict[tuple[str, ...], list[tuple[str, float, float]]]):
        self.lookup = lookup

    def recommend(self, basket: Sequence[str], top_n: int = 10) -> List[str]:
        seen: set[str] = set()
        scores: dict[str, tuple[float, float]] = {}
        basket_set = {str(item) for item in basket if item}
        if not basket_set:
            return []

        for antecedent, targets in self.lookup.items():
            if not set(antecedent).issubset(basket_set):
                continue
            for sku, confidence, lift in targets:
                if sku in basket_set:
                    continue
                current = scores.get(sku)
                candidate = (confidence, lift)
                if current is None or candidate > current:
                    scores[sku] = candidate

        ordered = sorted(scores.items(), key=lambda item: (-item[1][0], -item[1][1]))
        return [sku for sku, _ in ordered[:top_n]]


class Command(BaseCommand):
    help = "Train association-rule recommendations from a CSV of transactions and export a joblib model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--transactions",
            default="adminpanel/datasets/transactions.csv",
            help="Path to the transactions CSV. Accepts either wide format (one basket per row) or long format with transaction_id + sku columns.",
        )
        parser.add_argument(
            "--min-support",
            dest="min_support",
            type=float,
            default=0.002,
            help="Minimum itemset support used by the apriori algorithm (default: 0.002).",
        )
        parser.add_argument(
            "--min-confidence",
            dest="min_confidence",
            type=float,
            default=0.2,
            help="Minimum confidence for generated rules (default: 0.2).",
        )
        parser.add_argument(
            "--min-lift",
            dest="min_lift",
            type=float,
            default=1.05,
            help="Minimum lift for generated rules (default: 1.05).",
        )
        parser.add_argument(
            "--max-antecedent",
            dest="max_antecedent",
            type=int,
            default=3,
            help="Maximum size for rule antecedents to keep (default: 3).",
        )
        parser.add_argument(
            "--output",
            dest="output",
            default="adminpanel/mlmodels/b2c_products_500_transactions_50k.joblib",
            help="Destination path for the trained recommender (default: adminpanel/mlmodels/b2c_products_500_transactions_50k.joblib).",
        )
        parser.add_argument(
            "--summary",
            dest="summary",
            action="store_true",
            help="Print a JSON summary of the top rules after training.",
        )

    def handle(self, *args, **options):
        transactions_path = Path(options["transactions"]).resolve()
        if not transactions_path.exists():
            raise CommandError(f"Transactions file not found: {transactions_path}")

        self.stdout.write(f"Loading transactions from {transactions_path} …")
        df = pd.read_csv(transactions_path)
        baskets = self._extract_baskets(df)
        if not baskets:
            raise CommandError("No baskets could be extracted from the provided dataset.")

        self.stdout.write(f"Loaded {len(baskets):,} baskets.")
        encoder = TransactionEncoder()
        encoded_array = encoder.fit(baskets).transform(baskets)
        encoded_df = pd.DataFrame(encoded_array, columns=encoder.columns_)

        min_support = float(options["min_support"])
        self.stdout.write(f"Mining frequent itemsets (min_support={min_support}) …")
        frequent_itemsets = apriori(encoded_df, min_support=min_support, use_colnames=True)
        if frequent_itemsets.empty:
            raise CommandError("No frequent itemsets found. Try lowering --min-support or cleaning the dataset.")

        min_confidence = float(options["min_confidence"])
        min_lift = float(options["min_lift"])
        self.stdout.write(
            f"Generating association rules (min_confidence={min_confidence}, min_lift={min_lift}) …"
        )
        rules_df = association_rules(
            frequent_itemsets,
            metric="confidence",
            min_threshold=min_confidence,
        )
        if rules_df.empty:
            raise CommandError("No rules generated at the requested thresholds.")

        rules_df = rules_df[rules_df["lift"] >= min_lift]
        max_antecedent = int(options["max_antecedent"])
        rules_df = rules_df[rules_df["antecedents"].apply(lambda x: len(x) <= max_antecedent)]
        rules_df = rules_df[rules_df["consequents"].apply(lambda x: len(x) == 1)]
        rules_df = rules_df.sort_values(["confidence", "lift"], ascending=False).reset_index(drop=True)

        if rules_df.empty:
            raise CommandError("All generated rules were filtered out. Try relaxing --min-lift or --max-antecedent.")

        self.stdout.write(f"Keeping {len(rules_df):,} high-quality rules.")

        lookup: dict[tuple[str, ...], list[tuple[str, float, float]]] = defaultdict(list)
        for _, row in rules_df.iterrows():
            antecedent = tuple(sorted(str(item) for item in row["antecedents"]))
            consequent = next(iter(row["consequents"]))
            lookup[antecedent].append((str(consequent), float(row["confidence"]), float(row["lift"])))

        # Sort each target list by confidence then lift so recommend() can be deterministic.
        sorted_lookup = {
            antecedent: sorted(targets, key=lambda item: (-item[1], -item[2]))
            for antecedent, targets in lookup.items()
        }

        output_path = Path(options["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(RuleRecommender(sorted_lookup), output_path)

        self.stdout.write(self.style.SUCCESS(f"Saved trained association rules model to {output_path}"))

        if options.get("summary"):
            preview = []
            for antecedent, targets in list(sorted_lookup.items())[:25]:
                preview.append(
                    {
                        "antecedent": list(antecedent),
                        "recommendations": [
                            {"sku": sku, "confidence": conf, "lift": lift}
                            for sku, conf, lift in targets[:5]
                        ],
                    }
                )
            self.stdout.write(json.dumps(preview, indent=2))

    def _extract_baskets(self, df: pd.DataFrame) -> List[List[str]]:
        """Support both long-form (transaction_id, sku) and wide-form baskets."""
        columns = {col.lower(): col for col in df.columns}
        has_long_format = {"transaction_id", "basket_id", "order_id"}.intersection(columns)
        sku_column = columns.get("sku")

        if has_long_format and sku_column:
            transaction_col = columns[(has_long_format).pop()]
            grouped = df[[transaction_col, sku_column]].dropna()
            grouped[sku_column] = grouped[sku_column].astype(str).str.strip()
            grouped = grouped[grouped[sku_column] != ""]
            baskets_series = grouped.groupby(transaction_col)[sku_column].apply(list)
            return [list(dict.fromkeys(basket)) for basket in baskets_series.tolist() if basket]

        # Fallback: treat each row as a basket with SKU values spread across columns.
        baskets: List[List[str]] = []
        skip_tokens = {"transaction", "basket", "order", "id"}
        for _, row in df.iterrows():
            items: List[str] = []
            for col, value in row.items():
                if any(token in col.lower() for token in skip_tokens):
                    continue
                if pd.isna(value):
                    continue
                if isinstance(value, (int, float)):
                    if value <= 0:
                        continue
                    item = str(col).strip()
                else:
                    item = str(value).strip()
                    if not item or item.lower() in {"nan", "none", "0"}:
                        continue
                items.append(item)
            if items:
                baskets.append(list(dict.fromkeys(items)))
        return baskets
