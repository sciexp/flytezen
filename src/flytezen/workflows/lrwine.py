from dataclasses import asdict, make_dataclass
from pprint import pformat
from typing import Any, Dict, Optional, Tuple, Type

import joblib
import pandas as pd

# from dataclasses_json import DataClassJsonMixin as DataClassJSONMixin
from flytekit import task, workflow
from flytekit.types.file import JoblibSerializedFile
from mashumaro.mixins.json import DataClassJSONMixin
from sklearn.datasets import load_wine
from sklearn.linear_model import LogisticRegression

from flytezen.configuration import create_dataclass_from_callable
from flytezen.logging import configure_logging

logger = configure_logging("flytezen.workflows.lrwine")

# This is an optional dictionary that can be used to override the
# default types and values inferred from the callable if necessary
# or required. For this example, we provide commented out defaults
# to illustrate the types that are inferred from the callable and
# the ability to override them.
custom_types_defaults: Dict[str, Tuple[Type, Any]] = {
    # "penalty": (str, "l2"),
    # "dual": (bool, False),
    # "tol": (float, 1e-4),
    # "C": (float, 1.0),
    # "fit_intercept": (bool, True),
    # "intercept_scaling": (int, 1),
    "class_weight": (Optional[dict], None),
    "random_state": (Optional[int], None),
    # "solver": (str, "lbfgs"),
    "max_iter": (int, 2000),
    # "multi_class": (str, "auto"),
    # "verbose": (int, 0),
    # "warm_start": (bool, False),
    "n_jobs": (Optional[int], None),
    "l1_ratio": (Optional[float], None),
}

logistic_regression_fields = create_dataclass_from_callable(
    LogisticRegression, custom_types_defaults
)

LogisticRegressionInterface = make_dataclass(
    "LogisticRegressionInterface",
    logistic_regression_fields,
    bases=(DataClassJSONMixin,),
    # TODO: Python 3.12, https://github.com/python/cpython/pull/102104
    # module=__name__,
)
LogisticRegressionInterface.__module__ = __name__


sample_columns = [
    "alcohol",
    "malic_acid",
    "ash",
    "alcalinity_of_ash",
    "magnesium",
    "total_phenols",
    "flavanoids",
    "nonflavanoid_phenols",
    "proanthocyanins",
    "color_intensity",
    "hue",
    "od280/od315_of_diluted_wines",
    "proline",
    "target",
]

sample_data = [
    [13.0, 1.5, 2.3, 15.0, 110, 2.5, 3.0, 0.3, 1.5, 4.0, 1.0, 3.0, 1000, 0],
    [14.0, 1.6, 2.4, 16.0, 120, 2.6, 3.1, 0.4, 1.6, 5.0, 1.1, 3.1, 1100, 1],
    [12.5, 1.4, 2.2, 14.0, 100, 2.4, 2.9, 0.2, 1.4, 3.5, 0.9, 2.9, 900, 2],
]

# sample_columns = [
#     "alcohol",
#     "target",
# ]

# sample_data = [
#     [13.0, 0],
#     [14.0, 1],
#     [12.5, 2],
# ]


@task
def get_data() -> pd.DataFrame:
    """
    Get the wine dataset.
    """
    # import time

    # time.sleep(3600)
    return load_wine(as_frame=True).frame


@task
def process_data(
    data: pd.DataFrame = pd.DataFrame(data=sample_data, columns=sample_columns),
) -> pd.DataFrame:
    """
    Simplify the task from a 3-class to a binary classification problem.
    """
    return data.assign(target=lambda x: x["target"].where(x["target"] == 0, 1))


@task
def train_model(
    data: pd.DataFrame = pd.DataFrame(data=sample_data, columns=sample_columns),
    logistic_regression: LogisticRegressionInterface = LogisticRegressionInterface(
        max_iter=1200
    ),
) -> JoblibSerializedFile:
    """
    Train a model on the wine dataset.
    """
    features = data.drop("target", axis="columns")
    target = data["target"]
    logger.info(f"{pformat(logistic_regression)}\n\n")
    model = LogisticRegression(**asdict(logistic_regression))
    model_path = "logistic_regression_model.joblib"
    joblib.dump(model, model_path)
    model_file = JoblibSerializedFile(model_path)
    return model_file


@workflow
def training_workflow(
    logistic_regression: LogisticRegressionInterface = LogisticRegressionInterface(
        max_iter=2000
    ),
) -> JoblibSerializedFile:
    """
    Put all of the steps together into a single workflow.
    """
    data = get_data()
    processed_data = process_data(data=data)
    return train_model(
        data=processed_data,
        logistic_regression=logistic_regression,
    )


if __name__ == "__main__":
    # Execute the workflow, simply by invoking it like a function and passing in
    # the necessary parameters
    print(f"Running process_data() { process_data() }")
    print(f"Running training_workflow() { training_workflow() }")

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


# The following can be used to test dynamic dataclass construction
# using the dataclasses_json library instead of mashumaro,

# from dataclasses_json import dataclass_json
# from flytezen.configuration import create_dataclass_from_callable_json
# logistic_regression_custom_types: Dict[str, Type[Optional[Any]]] = {
#     "penalty": Optional[str],
#     "class_weight": Optional[dict],
#     "random_state": Optional[int],
#     "n_jobs": Optional[int],
#     "l1_ratio": Optional[float],
# }

# LogisticRegressionInterface = dataclass_json(
#     dataclass(
#         create_dataclass_from_callable_json(
#             LogisticRegression, logistic_regression_custom_types
#         )
#     )
# )
