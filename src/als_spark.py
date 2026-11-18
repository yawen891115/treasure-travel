"""Collaborative filtering with PySpark ALS (Alternating Least Squares).

ALS learns a short vector for every user and every place so that
user_vector . place_vector is high for places the user would visit.
"""

import os

import numpy as np


def _to_matrix(factor_df, n_rows, rank):
    """Spark returns factors as rows (id, [f1, f2, ...]); put them in a numpy matrix."""
    pdf = factor_df.toPandas()
    matrix = np.zeros((n_rows, rank), dtype=np.float32)
    if len(pdf):
        matrix[pdf["id"].to_numpy()] = np.vstack(pdf["features"].to_numpy())
    return matrix


def train_als(train, n_users, n_items, rank=32, reg=0.1, alpha=10.0, iterations=12, seed=42):
    """Train implicit-feedback ALS on train visits. Returns (user_factors, item_factors)."""
    os.environ.setdefault("PYSPARK_PYTHON", "python")
    from pyspark.ml.recommendation import ALS
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("treasure-travel-als")
        .config("spark.driver.memory", "4g")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")  # fast pandas <-> Spark
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        # Implicit ALS uses positive strengths as likes and negative strengths as dislikes.
        # Ratings >= 4 match the evaluation definition of positive preference.
        data = train[["user_idx", "item_idx", "rating"]].rename(columns={"rating": "strength"})
        data["strength"] = data["strength"] - 3.0
        data = data.astype({"user_idx": "int32", "item_idx": "int32", "strength": "float32"})
        sdf = spark.createDataFrame(data)
        als = ALS(
            userCol="user_idx",
            itemCol="item_idx",
            ratingCol="strength",
            rank=rank,
            regParam=reg,
            alpha=alpha,
            maxIter=iterations,
            implicitPrefs=True,
            coldStartStrategy="drop",
            seed=seed,
        )
        model = als.fit(sdf)
        user_factors = _to_matrix(model.userFactors, n_users, rank)
        item_factors = _to_matrix(model.itemFactors, n_items, rank)
    finally:
        spark.stop()
    return user_factors, item_factors


def als_scores(user_factors, item_factors, users):
    """Predicted preference for every (user, place): matrix users x places."""
    return (user_factors[users] @ item_factors.T).astype(np.float32)
