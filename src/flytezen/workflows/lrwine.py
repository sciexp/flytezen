from dataclasses import asdict, dataclass
from pprint import pformat
from typing import Any, Dict, Optional, Type

import pandas as pd
from dataclasses_json import dataclass_json
from flytekit import task, workflow
from sklearn.datasets import load_wine
from sklearn.linear_model import LogisticRegression

from flytezen.configuration import create_dataclass_from_callable
from flytezen.logging import configure_logging

logger = configure_logging("lrwine")

logistic_regression_custom_types: Dict[str, Type[Optional[Any]]] = {
    "penalty": Optional[str],
    "class_weight": Optional[dict],
    "random_state": Optional[int],
    "n_jobs": Optional[int],
    "l1_ratio": Optional[float],
}

LogisticRegressionInterface = dataclass_json(
    dataclass(
        create_dataclass_from_callable(
            LogisticRegression, logistic_regression_custom_types
        )
    )
)


@task
def get_data() -> pd.DataFrame:
    """Get the wine dataset."""
    # import time

    # time.sleep(3600)
    return load_wine(as_frame=True).frame


@task
def process_data(data: pd.DataFrame) -> pd.DataFrame:
    """Simplify the task from a 3-class to a binary classification problem."""
    return data.assign(target=lambda x: x["target"].where(x["target"] == 0, 1))


@task
def train_model(
    data: pd.DataFrame, logistic_regression: LogisticRegressionInterface
) -> LogisticRegression:
    """Train a model on the wine dataset."""
    features = data.drop("target", axis="columns")
    target = data["target"]
    logger.info(f"{pformat(logistic_regression)}\n\n")
    LogisticRegressionInstance = LogisticRegression(
        **asdict(logistic_regression)
    )
    return LogisticRegressionInstance.fit(features, target)


@workflow
def training_workflow(
    logistic_regression: LogisticRegressionInterface = LogisticRegressionInterface(
        max_iter=2000
    ),
) -> LogisticRegression:
    """Put all of the steps together into a single workflow."""
    data = get_data()
    processed_data = process_data(data=data)
    return train_model(
        data=processed_data,
        logistic_regression=logistic_regression,
    )


# The following can be used to test dynamic dataclass construction
# in the case where there are multiple inputs of distinct types,
# by commenting @workflow above and uncommenting the following:
#
# from sklearn.linear_model import LinearRegression, LogisticRegression

# linear_regression_custom_types: Dict[str, Type[Optional[Any]]] = {
#     "n_jobs": Optional[int],
# }

# LinearRegressionInterface = dataclass_json(
#     dataclass(
#         create_dataclass_from_callable(
#             LinearRegression, linear_regression_custom_types
#         )
#     )
# )
# @workflow
# def training_workflow(
#     logistic_regression: LogisticRegressionInterface = LogisticRegressionInterface(
#         max_iter=2000
#     ),
#     linear_regression: LinearRegressionInterface = LinearRegressionInterface(),
# ) -> LogisticRegression:
#     """Put all of the steps together into a single workflow."""
#     data = get_data()
#     processed_data = process_data(data=data)
#     return train_model(
#         data=processed_data,
#         logistic_regression=logistic_regression,
#     )