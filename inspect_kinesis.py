import logging
import sys
import os
import clr

kinesis_path = r"C:\Program Files\Thorlabs\Kinesis"

# make sure Windows loader can find dependent DLLs
os.environ["PATH"] = kinesis_path + ";" + os.environ["PATH"]

# make Python see the assemblies
sys.path.append(kinesis_path)

# load assemblies
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.GenericMotorCLI")

# import namespaces
import Thorlabs.MotionControl.DeviceManagerCLI as dev
import Thorlabs.MotionControl.GenericMotorCLI as gm

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger.info("DeviceManagerCLI namespace:")
logger.info("%s", dir(dev))

logger.info("GenericMotorCLI namespace:")
logger.info("%s", dir(gm))
