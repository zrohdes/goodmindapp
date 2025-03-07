# goodmind
simple project to build mental wellbeing to help people

import os

# Set this before any other imports
os.environ['PYTHONHTTPSVERIFY'] = '0'

from hume.legacy import HumeVoiceClient, VoiceConfig
from hume import MicrophoneInterface
import asyncio


async def main() -> None:
    # Retrieve the Hume API key
    HUME_API_KEY = "VdTPDQB085Asn41CwxyJJada56OCk13QLAylMRA9TX7KjpoM"
    #HUME_API_KEY = os.getenv("HUME_API_KEY") or "YOUR_HUME_API_KEY_HERE"

    # Connect to Hume
    client = HumeVoiceClient(HUME_API_KEY)

    # Start streaming
    async with client.connect() as socket:
        await MicrophoneInterface.
        await MicrophoneInterface.start(socket, allow_user_interrupt=True)


asyncio.run(main())
