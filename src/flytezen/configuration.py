import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Type, get_type_hints


def infer_type_from_default(default: Any) -> Any:
    """
    Infers the type from the default value of a parameter. Supports basic types like bool, int, float, str, list, and dict.

    Args:
        default (Any): The default value of a parameter.

    Returns:
        Type: The inferred type based on the default value, or Any if the type cannot be inferred.

    Examples:
        >>> infer_type_from_default(5)
        <class 'int'>
        >>> infer_type_from_default(True)
        <class 'bool'>
        >>> infer_type_from_default("example")
        <class 'str'>
        >>> infer_type_from_default(None)  # For None, it defaults to Any
        typing.Any
    """
    if isinstance(default, bool):
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
        return Any


def create_dataclass_from_callable(callable_obj: Callable) -> Type:
    """
    Creates a dataclass from a callable object (such as a function or class constructor).
    This dataclass includes all parameters of the callable as fields, with types inferred or
    directly taken from type hints. Fields are assigned default values based on the callable's
    signature.

    Args:
        callable_obj (Callable): The callable object from which to create a dataclass.

    Returns:
        Type: A new dataclass type that represents the interface of the callable.

    Examples:
        >>> from sklearn.linear_model import LogisticRegression
        >>> LogisticRegressionInterface = create_dataclass_from_callable(LogisticRegression)
        >>> hasattr(LogisticRegressionInterface, 'fit_intercept')
        True
        >>> LogisticRegressionInterface.__annotations__['fit_intercept']
        <class 'bool'>

        # Testing with a simple function
        >>> def example_func(a: int, b: str = 'hello', c: bool = False):
        ...     pass
        >>> ExampleFuncInterface = create_dataclass_from_callable(example_func)
        >>> ExampleFuncInterface.__annotations__
        {'a': <class 'int'>, 'b': <class 'str'>, 'c': <class 'bool'>}
        >>> example_instance = ExampleFuncInterface(a=5)
        >>> example_instance.b
        'hello'
    """
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

        field_type = type_hints.get(name, infer_type_from_default(param.default))
        default = param.default if param.default is not inspect.Parameter.empty else field(default_factory=lambda: None)
        class_attrs[name] = field(default=default) if default is field else default
        class_attrs["__annotations__"][name] = field_type

    dataclass_name = f"{callable_obj.__name__}Interface"
    new_class = type(dataclass_name, (object,), class_attrs)
    return dataclass(new_class)
