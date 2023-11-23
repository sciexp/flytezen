from dataclasses import dataclass
from pprint import pformat
from typing import Any, Dict, Optional, Type

from dataclasses_json import dataclass_json
from hydra_zen import builds, instantiate
from sklearn.linear_model import LogisticRegression

from flytezen.configuration import create_dataclass_from_callable
from flytezen.logging import configure_logging

logger = configure_logging("dataclass_dict")

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


def pformat_log(x):
    return logger.info(f"{pformat(x)}\n")


if __name__ == "__main__":
    logger.info("I(B(LogisticRegressionInterface):\n")
    pformat_log(instantiate(builds(LogisticRegressionInterface)))
    logger.info("Dict\\[str, DataClass]:\n")
    pformat_log({"logistic_regression": LogisticRegressionInterface()})
    logger.info("I(B(Dict\\[str, B(DataClass)])):\n")
    LRDataClassDict = instantiate(
        builds(
            dict,
            {"logistic_regression": builds(LogisticRegressionInterface)},
            hydra_convert="all",
        )
    )
    pformat_log(LRDataClassDict)
    logger.info(
        f"Type of LR dict value:\n{type(LRDataClassDict['logistic_regression'])}\n"
    )
    logger.info("I(B(Dict\\[str, B(LogisticRegression)])):\n")
    pformat_log(
        instantiate(
            builds(
                dict,
                {"logistic_regression": builds(LogisticRegression)},
            )
        )
    )
