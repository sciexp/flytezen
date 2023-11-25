import dataclasses
import inspect
import sys
from dataclasses import field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    get_type_hints,
)

from mashumaro.mixins.json import DataClassJSONMixin
from sklearn.linear_model import LogisticRegression


def infer_type_from_default(value: Any) -> Type:
    """
    Infers or imputes a type from the default value of a parameter.
    Args:
        value: The default value of the parameter.
    Returns:
        The inferred type.
    """
    if value is None:
        return Optional[Any]
    elif value is inspect.Parameter.empty:
        return Any
    else:
        return type(value)


def create_dataclass_from_callable(
    callable_obj: Callable,
    overrides: Optional[Dict[str, Tuple[Type, Any]]] = None,
) -> List[Tuple[str, Type, Any]]:
    """
    Creates the fields of a dataclass from a `Callable` that includes all
    parameters of the callable as typed fields with default values inferred or
    taken from type hints. The function also accepts a dictionary containing
    parameter names together with a tuple of a type and default to allow
    specification of or override (un)typed defaults from the target callable.

    Args:
        callable_obj (Callable): The callable object to create a dataclass from.
        overrides (Optional[Dict[str, Tuple[Type, Any]]]): Dictionary to
        override inferred types and default values. Each dict value is a tuple
        (Type, default_value).

    Returns:
        Fields that can be used to construct a new dataclass type that
        represents the interface of the callable.

    Examples:
        >>> from pprint import pprint
        >>> custom_types_defaults: Dict[str, Tuple[Type, Any]] = {
        ...     "penalty": (str, "l2"),
        ...     "class_weight": (Optional[dict], None),
        ...     "random_state": (Optional[int], None),
        ...     "max_iter": (int, 2000),
        ...     "n_jobs": (Optional[int], None),
        ...     "l1_ratio": (Optional[float], None),
        ... }
        >>> fields = create_dataclass_from_callable(LogisticRegression, custom_types_defaults)
        >>> LogisticRegressionInterface = dataclasses.make_dataclass(
        ...     "LogisticRegressionInterface", fields, bases=(DataClassJSONMixin,)
        ... )
        >>> lr_instance = LogisticRegressionInterface()
        >>> isinstance(lr_instance, DataClassJSONMixin)
        True
        >>> pprint(lr_instance)
        LogisticRegressionInterface(penalty='l2',
                                    dual=False,
                                    tol=0.0001,
                                    C=1.0,
                                    fit_intercept=True,
                                    intercept_scaling=1,
                                    class_weight=None,
                                    random_state=None,
                                    solver='lbfgs',
                                    max_iter=2000,
                                    multi_class='auto',
                                    verbose=0,
                                    warm_start=False,
                                    n_jobs=None,
                                    l1_ratio=None)
    """
    if inspect.isclass(callable_obj):
        func = callable_obj.__init__
    else:
        func = callable_obj

    signature = inspect.signature(func)
    type_hints = get_type_hints(func)

    fields = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue

        if overrides and name in overrides:
            field_type, default_value = overrides[name]
        else:
            inferred_type = infer_type_from_default(param.default)
            field_type = type_hints.get(name, inferred_type)
            default_value = (
                param.default
                if param.default is not inspect.Parameter.empty
                else dataclasses.field(default_factory=lambda: None)
            )

        fields.append((name, field_type, default_value))

    return fields


#-----------
# Deprecated
#-----------

class TypeInferenceError(Exception):
    pass


def infer_type_from_default_json(
    default: Any, name: str, custom_types: Optional[Dict[str, Type]] = None
) -> Type:
    """
    Infers the type from the default value of a parameter. Supports basic types
    like bool, int, float, str, list, and dict.

    Args:
        default: The default value of a parameter.
        name: The name of the parameter.
        custom_types: A dictionary of custom types for specific parameter names.

    Returns:
        The inferred type based on the default value, or Any if the type cannot be inferred.

    Raises:
        TypeInferenceError: If the type cannot be inferred and is not provided in custom_types.

    Examples:
        >>> infer_type_from_default_json(5, "example_int")
        <class 'int'>
        >>> infer_type_from_default_json(True, "example_bool")
        <class 'bool'>
        >>> infer_type_from_default_json("example", "example_str")
        <class 'str'>
        >>> infer_type_from_default_json(None, "example_none")  # Raises an exception
        Traceback (most recent call last):
        ...
        flytezen.configuration.TypeInferenceError: Type for parameter 'example_none' with default value None cannot be inferred.
        Add this parameter to the custom_types dictionary.
    """

    if custom_types is None:
        custom_types = {}
    if name in custom_types:
        return custom_types[name]

    if default is None:
        type_inference_error_message = (
            f"Type for parameter '{name}' with default value None cannot be inferred.\n"
            "Add this parameter to the custom_types dictionary.\n"
        )
        raise TypeInferenceError(type_inference_error_message)

    if default is inspect.Parameter.empty:
        type_inference_error_message = (
            f"Type for parameter '{name}' with no default value cannot be inferred.\n"
            "Add this parameter to the custom_types dictionary.\n"
        )
        raise TypeInferenceError(type_inference_error_message)

    elif isinstance(default, bool):
        return bool
    elif isinstance(default, int):
        return int
    elif isinstance(default, float):
        return float
    elif isinstance(default, str):
        return str
    elif isinstance(default, list):
        return list
    elif isinstance(default, dict):
        return dict
    else:
        type_inference_error_message = (
            f"Type for parameter '{name}' with default value {default} cannot be inferred.\n"
            "Add this parameter to the custom_types dictionary.\n"
        )
        raise TypeInferenceError(type_inference_error_message)


def create_dataclass_from_callable_json(
    callable_obj: Callable, custom_types: Optional[Dict[str, Type]] = None
) -> Type:
    """
    Creates a dataclass from a callable object (such as a function or class
    constructor). This dataclass includes all parameters of the callable as
    fields, with types inferred or directly taken from type hints. Fields are
    assigned default values based on the callable's signature.

    Args:
        callable_obj: The callable object from which to create a dataclass.
        custom_types: An optional dictionary for overriding inferred types.

    Returns:
        A new dataclass type that represents the interface of the callable.

    Examples:
        >>> from dataclasses import dataclass
        >>> from dataclasses_json import dataclass_json
        ... # Example with sklearn's LogisticRegression
        >>> from sklearn.linear_model import LogisticRegression
        >>> logistic_regression_custom_types = {
        ...     "penalty": Optional[str],
        ...     "class_weight": Optional[dict],
        ...     "random_state": Optional[int],
        ...     "n_jobs": Optional[int],
        ...     "l1_ratio": Optional[float],
        ... }
        >>> BaseLogisticRegressionInterface = create_dataclass_from_callable_json(
        ...     LogisticRegression, logistic_regression_custom_types
        ... )
        >>> hasattr(BaseLogisticRegressionInterface, 'fit_intercept')
        True

        # Extending the base class with additional methods or properties
        >>> class LogisticRegressionInterface(BaseLogisticRegressionInterface):
        ...     def additional_method(self):
        ...         return "Some custom behavior"
        >>> LogisticRegressionInterface = dataclass_json(dataclass(LogisticRegressionInterface))
        >>> hasattr(LogisticRegressionInterface, 'additional_method')
        True

        # Using decorators without extending the base class
        >>> @dataclass_json
        ... @dataclass
        ... class LogisticRegressionInterface(create_dataclass_from_callable_json(
        ...     LogisticRegression, logistic_regression_custom_types)):
        ...     pass
        >>> hasattr(LogisticRegressionInterface, 'fit_intercept')
        True

        # Testing with a simple function and custom types
        >>> def example_func(a: int, b='hello', c: bool=False):
        ...     pass
        >>> example_func_custom_types = {"b": str}
        >>> ExampleFuncInterface = dataclass_json(
        ...     dataclass(create_dataclass_from_callable_json(
        ...     example_func, example_func_custom_types
        ...     ))
        ... )
        Traceback (most recent call last):
        ...
        flytezen.configuration.TypeInferenceError: Type for parameter 'a' with no default value cannot be inferred.
        Add this parameter to the custom_types dictionary.
        >>> def example_func(a, b='hello', c: bool=False):
        ...     pass
        >>> example_func_custom_types = {"a": int, "b": str,}
        >>> ExampleFuncInterface = dataclass_json(
        ...     dataclass(create_dataclass_from_callable_json(
        ...     example_func, example_func_custom_types
        ...     ))
        ... )
        >>> example_instance = ExampleFuncInterface(a=5)
        >>> example_instance.b == 'hello'
        True
    """
    caller_module = sys._getframe(1).f_globals["__name__"]

    if inspect.isclass(callable_obj):
        func = callable_obj.__init__
    else:
        func = callable_obj

    signature = inspect.signature(func)
    type_hints = get_type_hints(func)

    class_attrs = {"__annotations__": {}}

    for name, param in signature.parameters.items():
        if name == "self":
            continue

        try:
            field_type = type_hints.get(
                name,
                infer_type_from_default_json(param.default, name, custom_types),
            )
        except TypeInferenceError as e:
            raise TypeInferenceError(str(e)) from e

        default = (
            param.default
            if param.default is not inspect.Parameter.empty
            else field(default_factory=lambda: None)
        )
        class_attrs[name] = (
            field(default=default) if default is field else default
        )
        class_attrs["__annotations__"][name] = field_type

    dataclass_name = f"{callable_obj.__name__}Interface"

    new_class = type(dataclass_name, (object,), class_attrs)
    new_class.__module__ = caller_module

    return new_class

#---------------
# End Deprecated
#---------------

if __name__ == "__main__":
    # Commented code here is primarily to support CLI or IDE debugger execution.
    # Otherwise, prefer to integrate tests and checks into the docstrings and
    # run pytest with `--xdoc` (default in this project).

    import pprint

    custom_types_defaults: Dict[str, Tuple[Type, Any]] = {
        # "penalty": (str, "l2"),
        # "dual": (bool, False),
        # "tol": (float, 1e-4),
        # "C": (float, 1.0),
        # "fit_intercept": (bool, True),
        # "intercept_scaling": (int, 1),
        # "class_weight": (Optional[dict], None),
        # "random_state": (Optional[int], None),
        # "solver": (str, "lbfgs"),
        "max_iter": (int, 2000),
        # "multi_class": (str, "auto"),
        # "verbose": (int, 0),
        # "warm_start": (bool, False),
        # "n_jobs": (Optional[int], None),
        # "l1_ratio": (Optional[float], None),
    }

    fields = create_dataclass_from_callable(
        LogisticRegression,
        custom_types_defaults,
        # {},
    )
    LogisticRegressionInterface = dataclasses.make_dataclass(
        "LogisticRegressionInterface", fields, bases=(DataClassJSONMixin,)
    )
    pprint.pprint(LogisticRegressionInterface())

    # from dataclasses import dataclass
    # from dataclasses_json import dataclass_json
    # from sklearn.linear_model import LogisticRegression
    # logistic_regression_custom_types = {
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
    # print("Annotations:", LogisticRegressionInterface.__annotations__)
    # print("Schema:", LogisticRegressionInterface().schema())
