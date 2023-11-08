from flytekit.remote import FlyteRemote
from flytekit.configuration import Config
from dotenv import load_dotenv
import os

load_dotenv()

WORKFLOW_PROJECT = os.getenv('WORKFLOW_PROJECT')
WORKFLOW_DOMAIN = os.getenv('WORKFLOW_DOMAIN')

if not WORKFLOW_PROJECT or not WORKFLOW_DOMAIN:
    raise ValueError("WORKFLOW_PROJECT and WORKFLOW_DOMAIN must be set in the .env file")

remote = FlyteRemote(config=Config.auto())

flyte_wf = remote.fetch_workflow(
    name="workflows.lrwine.training_workflow",
    project=WORKFLOW_PROJECT,
    domain=WORKFLOW_DOMAIN
)

execution = remote.execute(
    flyte_wf,
    inputs={"hyperparameters": {"C": 0.2}},
    project=WORKFLOW_PROJECT,
    domain=WORKFLOW_DOMAIN
)
