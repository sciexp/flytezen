"""
Constructs configurations for each leaf node in the supported
execution config tree:

    execution_config = {
        "LOCAL": {
            "SHELL": "LOCAL_SHELL",
            "CLUSTER": {
                "DEV": "LOCAL_CLUSTER_DEV",
                "PROD": "LOCAL_CLUSTER_PROD"
            }
        },
        "REMOTE": {
            "DEV": "REMOTE_DEV",
            "PROD": "REMOTE_PROD"
        }
    }

TODO: See notes on undesirably broad type annotations due to failure of
type-checking with appropriate annotations at the bottom of this file.
"""

from dataclasses import dataclass, field
from enum import Enum

from hydra_zen import make_custom_builds_fn


class ClusterMode(Enum):
    dev = "DEV"
    prod = "PROD"


class LocalMode(Enum):
    shell = "SHELL"
    cluster = "CLUSTER"


class ExecutionLocation(Enum):
    local = "LOCAL"
    remote = "REMOTE"


@dataclass
class ClusterConfig:
    mode: ClusterMode = field(default_factory=lambda: ClusterMode.dev)


@dataclass
class LocalConfig:
    mode: LocalMode = field(default_factory=lambda: LocalMode.shell)
    cluster_config: ClusterConfig = field(default_factory=ClusterConfig)


@dataclass
class ExecutionMode:
    location: ExecutionLocation = field(
        default_factory=lambda: ExecutionLocation.local
    )
    local_config: LocalConfig = field(default_factory=LocalConfig)
    remote_config: ClusterConfig = field(default_factory=ClusterConfig)


fbuilds = make_custom_builds_fn(populate_full_signature=True)
ClusterConfigConf = fbuilds(ClusterConfig)
LocalConfigConf = fbuilds(LocalConfig)
ExecutionModeConf = fbuilds(ExecutionMode)


# Local Shell Configuration
local_shell_config = ExecutionModeConf(
    location=ExecutionLocation.local,
    local_config=LocalConfigConf(
        mode=LocalMode.shell,
        cluster_config=None,  # not applicable for SHELL mode
    ),
    remote_config=None,  # not applicable for LOCAL location
)

# Local Cluster Dev Configuration
local_cluster_dev_config = ExecutionModeConf(
    location=ExecutionLocation.local,
    local_config=LocalConfigConf(
        mode=LocalMode.cluster,
        cluster_config=ClusterConfigConf(mode=ClusterMode.dev),
    ),
    remote_config=None,  # not applicable for LOCAL location
)

# Local Cluster Prod Configuration
local_cluster_prod_config = ExecutionModeConf(
    location=ExecutionLocation.local,
    local_config=LocalConfigConf(
        mode=LocalMode.cluster,
        cluster_config=ClusterConfigConf(mode=ClusterMode.prod),
    ),
    remote_config=None,  # not applicable for LOCAL location
)

# Remote Dev Configuration
remote_dev_config = ExecutionModeConf(
    location=ExecutionLocation.remote,
    local_config=None,  # not applicable for REMOTE location
    remote_config=ClusterConfigConf(mode=ClusterMode.dev),
)

# Remote Prod Configuration
remote_prod_config = ExecutionModeConf(
    location=ExecutionLocation.remote,
    local_config=None,  # not applicable for REMOTE location
    remote_config=ClusterConfigConf(mode=ClusterMode.prod),
)

if __name__ == "__main__":
    from pprint import pprint

    from hydra_zen import instantiate

    def ipprint(x):
        pprint(instantiate(x))

    ipprint(local_shell_config)
    ipprint(local_cluster_dev_config)
    ipprint(local_cluster_prod_config)
    ipprint(remote_dev_config)
    ipprint(remote_prod_config)


# Correct typing is given below; however, it leads to
# `Builds_DataClass is not a subclass of Dataclass` in each case
# @dataclass
# class ClusterConfig:
#     mode: ClusterMode = ClusterMode.dev

# @dataclass
# class LocalConfig:
#     mode: LocalMode = LocalMode.shell
#     cluster_config: ClusterConfig = ClusterConfig()

# @dataclass
# class ExecutionMode:
#     location: ExecutionLocation = ExecutionLocation.local
#     local_config: LocalConfig = LocalConfig()
#     remote_config: ClusterConfig = ClusterConfig()

# from typing import Type, TYPE_CHECKING
# from typing_extensions import TypeAlias
# TypeA: TypeAlias = A if TYPE_CHECKING else Any
# TypeClusterMode: TypeAlias = ClusterMode if TYPE_CHECKING else Any
# TypeLocalMode: TypeAlias = LocalMode if TYPE_CHECKING else Any
# TypeExecutionLocation: TypeAlias = ExecutionLocation if TYPE_CHECKING else Any
# TypeClusterConfig: TypeAlias = ClusterConfig if TYPE_CHECKING else Any
# TypeLocalConfig: TypeAlias = LocalConfig if TYPE_CHECKING else Any
# TypeExecutionMode: TypeAlias = ExecutionMode if TYPE_CHECKING else Any

# The type annotations on dataclass fields are undesirably broad
# See comments at the bottom of this file for more details
# @dataclass
# class ClusterConfig:
#     mode: Any


# @dataclass
# class LocalConfig:
#     mode: Any
#     cluster_config: Any = MISSING


# @dataclass
# class ExecutionMode:
#     location: Any
#     local_config: Any = MISSING
#     remote_config: Any = MISSING
