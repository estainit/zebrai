import debugpy
import uvicorn
from main import app

# Allow other computers to attach to debugpy at this IP address and port.
debugpy.listen(('0.0.0.0', 5678))

# Pause the program until a remote debugger is attached
print("Waiting for debugger to attach...")
debugpy.wait_for_client()
print("Debugger attached!")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 